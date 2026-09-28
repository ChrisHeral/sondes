# sondes

Sonde externe des sites hébergés sur le VPS (`achflow.fr`, `aplusibdx.fr`, `panono.fr`,
`monpetittricycle.fr`), lancée toutes les 5 minutes par GitHub Actions.

Pour chaque site : la page d'accueil en 200 **avec un texte témoin**, la redirection de `www`,
un certificat valable au moins 14 jours et, pour Panono, une route qui lit la base. Un échec
n'est retenu que s'il résiste à une seconde tentative 30 s plus tard (un déploiement coupe
quelques secondes).

Dépôt **public** parce que les minutes Actions y sont illimitées. Il ne contient aucun secret.

## Alerte : Healthchecks.io

Chaque passage réussi est signalé à l'URL `HEALTHCHECKS_URL` (secret du dépôt), un échec à
`…/fail` avec le rapport. Réglage du check : **période 5 min, grâce 20 min** — le cron de GitHub
glisse souvent de 10 à 15 minutes, une grâce plus courte donnerait de fausses alertes.

⚠️ L'absence de signal alerte elle aussi, et c'est voulu : GitHub coupe les tâches planifiées
d'un dépôt public resté 60 jours sans activité. On l'apprend alors par Healthchecks, qu'il suffit
de relancer depuis l'onglet Actions.

## Ce qu'elle ne verra jamais

Le filtrage DNS des domaines récents par certains réseaux (vécu le 20/09) : la sonde tourne
depuis un réseau qui résout normalement. Cf. `infra/docs/pieges-silencieux.md`.

## Ajouter un site

Une ligne dans `SITES` (`sonde.py`), avec un témoin lu dans la vraie page. Puis vérifier que
la sonde **échoue** avec un témoin faux avant de s'y fier.
