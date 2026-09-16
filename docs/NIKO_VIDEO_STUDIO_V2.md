# Niko Video Studio V2

Niko Video Studio V2 relie la préproduction **IA Studio Ciné** à la génération vidéo locale **WanGP**.

## Chaîne de production

1. Dans `ia-studio-cine`, préparer la Bible, le séquencier, le scénario, la shot list et le storyboard.
2. Ouvrir `wangp_bridge.html` dans le dépôt `ia-studio-cine` et utiliser **Exporter pour WanGP**.
3. Le bridge produit un fichier JSON au format `niko-video-project/v1` contenant les départements du projet et les prompts visuels détectés.
4. Dans Niko Video Studio V2, onglet **Séquence / Storyboard**, importer ce JSON.
5. Vérifier et éditer la timeline des plans (prompt et durée).
6. Choisir un modèle vidéo WanGP, la résolution, les FPS, les steps et le mode de continuité.
7. Lancer **Générer toute la séquence**.
8. Chaque plan est généré dans l’ordre puis assemblé automatiquement dans un MP4 final.

## Continuité visuelle

Deux modes sont proposés :

- **Frame précédente → plan suivant** : quand le modèle déclare l’image→vidéo, la dernière frame du plan précédent est extraite et réinjectée comme image de départ du plan suivant.
- **Prompt seulement** : la Bible de continuité est répétée dans chaque prompt sans chaînage d’image.

Une image de référence personnage/décor peut également être fournie. La même seed est utilisée pour toute la séquence afin de renforcer une identité visuelle commune, sans garantir à elle seule une identité parfaite.

## Timeline

La timeline importée est éditable avant génération :

- numéro du plan ;
- prompt vidéo ;
- durée en secondes.

Les prompts viennent des marqueurs `[PROMPT: ...]` produits par IA Studio Ciné. La Bible, la direction visuelle et la lumière sont importées comme contexte de continuité.

## Montage

Les vidéos générées sont assemblées avec MoviePy en H.264 / AAC dans :

`outputs/niko_video_studio_v2/`

Les frames de continuité temporaires sont stockées dans le même dossier.

## Lancement

### Windows

```bat
scripts\run_niko_video_studio_v2.bat
```

### Linux

```bash
bash scripts/run_niko_video_studio_v2.sh
```

L’interface écoute par défaut sur `127.0.0.1:7871`.

Pour un accès depuis un autre appareil du réseau local :

```bash
NIKO_VIDEO_HOST=0.0.0.0 bash scripts/run_niko_video_studio_v2.sh
```

Ne pas exposer directement l’interface sur Internet sans authentification, HTTPS et contrôle réseau adapté.

## Limites actuelles

- La cohérence entre plans dépend fortement du modèle sélectionné.
- Le chaînage de frame n’est utilisé que pour les modèles déclarant l’image→vidéo.
- L’assemblage actuel est un montage bout-à-bout ; transitions, mixage audio multipiste et étalonnage global pourront être ajoutés ensuite.
- Une machine disposant de l’environnement WanGP, des modèles locaux et du matériel compatible reste nécessaire pour la génération réelle.

## Licence

WanGP reste le moteur de génération. Niko Video Studio V2 conserve cette attribution et reste soumis à `LICENSE.txt` ainsi qu’aux licences des modèles et composants tiers utilisés.
