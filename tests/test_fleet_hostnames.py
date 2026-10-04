import pytest

from golem_fleet.fleet import hostnames


def test_hostname_normalises_whitespace_case_and_the_trailing_dot() -> None:
    hostname = hostnames.Hostname("  WWW.Lakin.CA.  ")

    assert hostname.text == "www.lakin.ca"
    assert str(hostname) == "www.lakin.ca"
    assert (
        hostnames.Hostname("implemus.sa-partner.com").router
        == "implemus-sa-partner-com"
    )


@pytest.mark.parametrize("text", ["   ", "."])
def test_hostname_that_normalises_to_nothing_is_rejected(text: str) -> None:
    with pytest.raises(hostnames.Empty) as refusal:
        hostnames.Hostname(text)
    assert refusal.value.args == (text,)


def test_published_normalises_and_lists_the_canonical_before_the_redirects() -> None:
    answering = hostnames.published("WWW.Lakin.CA.", "Lakin.CA.", "old.lakin.ca")

    assert [hostname.text for hostname in answering.hostnames] == [
        "www.lakin.ca",
        "lakin.ca",
        "old.lakin.ca",
    ]
    assert answering.canonical == hostnames.Hostname("www.lakin.ca")
    assert answering.redirected_from == (
        hostnames.Hostname("lakin.ca"),
        hostnames.Hostname("old.lakin.ca"),
    )


def test_a_redirect_equal_to_the_canonical_or_listed_twice_is_rejected() -> None:
    with pytest.raises(hostnames.RedirectIsCanonical) as canonical:
        hostnames.published("www.lakin.ca", "WWW.LAKIN.CA.")
    assert canonical.value.args == ("www.lakin.ca",)

    with pytest.raises(hostnames.RedirectListedTwice) as repeated:
        hostnames.published("www.lakin.ca", "lakin.ca", "lakin.ca")
    assert repeated.value.args == ("lakin.ca",)
