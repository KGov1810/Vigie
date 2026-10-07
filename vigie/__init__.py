"""Vigie — moteur du relais de lecture des offres d'emploi.

Organisation :
  config.py       variables d'environnement Vercel (Firebase, clés France Travail / Adzuna)
  auth.py         vérification du compte Firebase qui appelle le relais
  catalogue.py    liste des sites lisibles (aucune autre adresse n'est jamais lue)
  lecture.py      lecture d'un site : aiguillage, mots-clés en parallèle, tri, dédoublonnage
  communs.py      outils partagés : en-têtes HTTP, lieux d'Île-de-France, dates, format d'une offre
  pertinence.py   l'offre correspond-elle aux mots-clés, au métier recherché ?
  sources/        une fonction de lecture par site ou plateforme, rangées par famille
"""
