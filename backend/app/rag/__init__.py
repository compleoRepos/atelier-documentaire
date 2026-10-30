"""DICE — Documentary Intelligence & Context Engine (module RAG).

Ce paquet n'est jamais importé lorsque ``TRANSLATOR_RAG_MODE=DISABLED`` : les
points d'accroche (``app.application.jobs``, ``app.main``) l'importent
paresseusement, uniquement dans un mode actif. Il ne dépend d'aucun fichier de
la fermeture de mesure (moteur de traduction, constructeur de contexte,
pipeline documentaire, calculateurs de score).
"""
