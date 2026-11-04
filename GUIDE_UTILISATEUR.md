# Mode d'emploi — Wan2GP

**Type :** moteur lourd de génération image/vidéo, à installer sur un ordinateur ou serveur doté des ressources nécessaires. Ce n'est pas une PWA exécutable sur GitHub Pages.

## Prise en main

1. Lire le README du dépôt, les instructions du modèle choisi et les licences associées.
2. Vérifier le GPU, la mémoire vidéo, le système d'exploitation, Python et les pilotes demandés.
3. Préparer un environnement isolé. Installer les dépendances uniquement à partir de sources de confiance.
4. Démarrer le moteur selon les scripts officiellement fournis (wgp.py, Docker ou scripts documentés).
5. Télécharger ou sélectionner un modèle compatible, dans le respect de ses conditions d'utilisation.
6. Exécuter une génération courte de validation, consulter les logs puis ajuster les paramètres.
7. Exporter les fichiers résultants et contrôler leurs métadonnées avant toute diffusion.

## Dépannage

- **GPU ou CUDA absent :** vérifier les pilotes et le backend pris en charge ; un hébergement web statique ne résout pas cette limitation.
- **Mémoire insuffisante :** réduire la résolution/la durée et consulter les réglages d'optimisation documentés.
- **Téléchargement bloqué :** vérifier les quotas, le fournisseur et le réseau.
- **Interfaces inaccessibles :** vérifier les ports locaux et les règles pare-feu sans exposer inutilement le service sur Internet.

Aucune génération accélérée n'est garantie sur un téléphone. Ne stockez pas de jetons dans des dépôts publics.

[Studio Niko Hub](https://studio-niko-hub.vercel.app/) · [README original](https://github.com/Nikoju1977/Wan2GP)
