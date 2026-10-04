from dataclasses import dataclass

from golem_fleet.fault import Fault


class Empty(Fault):
    pass


class RedirectIsCanonical(Fault):
    pass


class RedirectListedTwice(Fault):
    pass


@dataclass(frozen=True)
class Hostname:
    text: str

    def __post_init__(self) -> None:
        normalised = self.text.strip().lower().removesuffix(".").strip()
        if not normalised:
            raise Empty(self.text)
        object.__setattr__(self, "text", normalised)

    @property
    def router(self) -> str:
        return self.text.replace(".", "-")

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class Internal:
    @property
    def hostnames(self) -> tuple[Hostname, ...]:
        return ()


@dataclass(frozen=True)
class Published:
    canonical: Hostname
    redirected_from: tuple[Hostname, ...] = ()

    def __post_init__(self) -> None:
        listed: set[str] = set()
        for redirect in self.redirected_from:
            if redirect == self.canonical:
                raise RedirectIsCanonical(self.canonical.text)
            if redirect.text in listed:
                raise RedirectListedTwice(redirect.text)
            listed.add(redirect.text)

    @property
    def hostnames(self) -> tuple[Hostname, ...]:
        return (self.canonical, *self.redirected_from)


Answering = Internal | Published


def published(canonical: str, *redirected_from: str) -> Published:
    return Published(
        Hostname(canonical),
        tuple(Hostname(text) for text in redirected_from),
    )
