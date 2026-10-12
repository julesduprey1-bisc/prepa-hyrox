"""Envoie le signal de la notification du matin à chaque téléphone abonné.

Le texte affiché est composé par l'app sur le téléphone (séances du jour, reports compris) :
ce script n'envoie aucune donnée, seulement un signal signé avec la clé VAPID.
"""
import json
import os
import pathlib
import sys

from pywebpush import WebPushException, webpush

fichier = pathlib.Path(__file__).with_name("abonnements.json")
if not fichier.exists():
    print("Aucun abonnement enregistré : rien à envoyer.")
    sys.exit(0)

cle = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
if not cle:
    sys.exit("Secret VAPID_PRIVATE_KEY manquant (Settings › Secrets and variables › Actions).")

abonnements = json.loads(fichier.read_text())
echecs = 0
for abo in abonnements:
    try:
        webpush(abo, data=None, vapid_private_key=cle,
                vapid_claims={"sub": "https://julesduprey1-bisc.github.io"}, ttl=4 * 3600)
        print("Envoyé à", abo["endpoint"][:40], "…")
    except WebPushException as e:
        echecs += 1
        print("Échec :", e)
sys.exit(1 if echecs == len(abonnements) else 0)
