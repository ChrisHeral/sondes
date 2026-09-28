#!/usr/bin/env python3
"""Sonde externe des sites du VPS, lancée depuis GitHub Actions — donc hors de la machine.

Les sondes internes ne voient pas une panne en amont de l'application : le 21/09 le site
est resté 31 minutes hors ligne, conteneurs sains et base joignable, parce que Caddy
n'avait plus de bloc pour le domaine. Seul un client extérieur voit ça.

Chaque passage réussi est signalé à Healthchecks.io ; un échec y est signalé en /fail.
L'absence de signal alerte aussi : c'est ce qui couvre une sonde qui ne tourne plus.

Usage : python3 sonde.py            (HEALTHCHECKS_URL facultative)
"""

from __future__ import annotations

import datetime as dt
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DELAI = 20.0
CERT_JOURS_MIN = 14
# Un déploiement coupe l'application quelques secondes : un échec n'est retenu que s'il
# survit à une seconde tentative.
REESSAI_APRES = 30.0
USER_AGENT = "sondes-chrisheral/1 (+https://github.com/ChrisHeral/sondes)"


@dataclass(frozen=True)
class Site:
    domaine: str
    temoin: str
    # Une URL qui traverse l'application jusqu'à sa base : une page d'accueil peut être
    # servie alors que la base est tombée.
    base: tuple[str, str] | None = None


SITES = [
    Site("achflow.fr", "Achflow"),
    Site("aplusibdx.fr", "Atelier A+I Bordeaux"),
    Site("panono.fr", "Panono", base=("/api/events", '"slug":')),
    Site("monpetittricycle.fr", "Mon Petit Tricycle"),
]


class SansRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def obtenir(url: str, suivre: bool = True) -> tuple[int, str, str]:
    """Renvoie (code, Location, corps). Un code d'erreur HTTP n'est pas une exception ici."""
    requete = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ouvreur = urllib.request.build_opener() if suivre else urllib.request.build_opener(SansRedirection)
    try:
        with ouvreur.open(requete, timeout=DELAI) as reponse:
            return reponse.status, reponse.headers.get("Location", ""), reponse.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as erreur:
        return erreur.code, erreur.headers.get("Location", ""), ""


def jours_de_certificat(domaine: str) -> int:
    contexte = ssl.create_default_context()
    with socket.create_connection((domaine, 443), timeout=DELAI) as brut:
        with contexte.wrap_socket(brut, server_hostname=domaine) as tls:
            fin = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
    return int((fin - time.time()) // 86400)


def controler(site: Site) -> list[str]:
    echecs: list[str] = []
    racine = f"https://{site.domaine}/"

    code, _, corps = obtenir(racine)
    if code != 200:
        echecs.append(f"{racine} → HTTP {code}")
    elif site.temoin not in corps:
        echecs.append(f"{racine} → 200 mais sans « {site.temoin} » (page d'erreur servie en 200 ?)")

    code, cible, _ = obtenir(f"https://www.{site.domaine}/", suivre=False)
    if code not in (301, 308) or cible.rstrip("/") != racine.rstrip("/"):
        echecs.append(f"www.{site.domaine} → HTTP {code} vers « {cible} », attendu une redirection vers {racine}")

    if site.base:
        chemin, temoin = site.base
        code, _, corps = obtenir(f"https://{site.domaine}{chemin}")
        if code != 200 or temoin not in corps:
            echecs.append(f"{site.domaine}{chemin} → HTTP {code}, témoin {temoin} {'présent' if temoin in corps else 'absent'}")

    jours = jours_de_certificat(site.domaine)
    if jours < CERT_JOURS_MIN:
        echecs.append(f"{site.domaine} : certificat valable encore {jours} jours seulement")
    return echecs


def controler_avec_reessai(site: Site) -> list[str]:
    try:
        echecs = controler(site)
    except (OSError, ssl.SSLError) as erreur:
        echecs = [f"{site.domaine} : {type(erreur).__name__} — {erreur}"]
    if not echecs:
        return []
    time.sleep(REESSAI_APRES)
    try:
        return controler(site)
    except (OSError, ssl.SSLError) as erreur:
        return [f"{site.domaine} : {type(erreur).__name__} — {erreur}"]


def signaler(rapport: str, succes: bool) -> None:
    url = os.environ.get("HEALTHCHECKS_URL", "").strip()
    if not url:
        print("(HEALTHCHECKS_URL absente : aucun signal envoyé)")
        return
    cible = url if succes else f"{url.rstrip('/')}/fail"
    requete = urllib.request.Request(cible, data=rapport.encode("utf-8"), method="POST",
                                     headers={"User-Agent": USER_AGENT})
    urllib.request.urlopen(requete, timeout=DELAI).close()


def main() -> int:
    lignes: list[str] = []
    for site in SITES:
        echecs = controler_avec_reessai(site)
        lignes += [f"❌ {e}" for e in echecs] or [f"✅ {site.domaine}"]
    succes = not any(l.startswith("❌") for l in lignes)
    horodatage = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rapport = "\n".join([horodatage, *lignes])
    print(rapport)
    signaler(rapport, succes)
    return 0 if succes else 1


if __name__ == "__main__":
    sys.exit(main())
