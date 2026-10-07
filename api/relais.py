# -*- coding: utf-8 -*-
"""
Vigie mobile — relais de lecture des offres d'emploi (fonction serverless Vercel).

Le téléphone ne peut pas lire directement les sites carrières (Safari l'interdit),
ce relais le fait à sa place, en temps réel, à chaque actualisation :
  GET  /api/relais            -> configuration publique (Firebase + catalogue des sites)
  POST /api/relais            -> {"source": "<id>", "mots": [...]} : lit UN site, renvoie ses offres

Ce fichier ne contient que le point d'entrée HTTP ; la logique est dans le paquet vigie/
(voir vigie/__init__.py pour son organisation).

Sécurité :
  - seuls les sites du catalogue (vigie/catalogue.py) peuvent être lus, jamais une adresse arbitraire ;
  - chaque appel doit porter le jeton d'un compte Firebase de VOTRE projet.

Variables d'environnement (Vercel > Settings > Environment Variables) :
  FIREBASE_CONFIG        obligatoire : la configuration web Firebase (copier-coller tel quel)
  EMAILS_AUTORISES       conseillé   : e-mails autorisés à utiliser le relais, séparés par des virgules
  FRANCE_TRAVAIL_ID      facultatif  : identifiant client francetravail.io
  FRANCE_TRAVAIL_SECRET  facultatif  : clé secrète francetravail.io
  ADZUNA_ID              facultatif  : App ID developer.adzuna.com
  ADZUNA_KEY             facultatif  : App Key developer.adzuna.com
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# le paquet vigie/ est à la racine du projet, un niveau au-dessus de ce fichier
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vigie.auth import CompteRefuse, verifier_jeton  # noqa: E402
from vigie.catalogue import GROUPES, catalogue_public  # noqa: E402
from vigie.config import firebase_config  # noqa: E402
from vigie.lecture import _mots_propres, lire_source  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _json(self, code, contenu):
        corps = json.dumps(contenu, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):  # noqa: N802
        self._json(200, {
            "firebase": firebase_config(),
            "groupes": GROUPES,
            "catalogue": catalogue_public(),
        })

    def do_POST(self):  # noqa: N802
        try:
            longueur = min(int(self.headers.get("Content-Length") or 0), 20000)
            demande = json.loads(self.rfile.read(longueur) or b"{}")
        except Exception:
            return self._json(400, {"etat": "erreur", "offres": [], "detail": "requête illisible"})
        try:
            verifier_jeton(self.headers.get("Authorization", ""))
        except CompteRefuse as e:
            return self._json(403, {"etat": "erreur", "offres": [], "detail": str(e)})
        except PermissionError as e:
            return self._json(401, {"etat": "erreur", "offres": [], "detail": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"etat": "erreur", "offres": [], "detail": f"vérification impossible : {e}"})
        try:
            resultat = lire_source(str(demande.get("source", "")), _mots_propres(demande.get("mots")))
        except Exception as e:  # noqa: BLE001
            resultat = {"etat": "erreur", "offres": [], "detail": str(e)[:200]}
        self._json(200, resultat)

    def log_message(self, *args):  # journal Vercel suffisant
        pass
