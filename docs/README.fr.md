# Blocksmith

[English](../README.md) · [Español](README.es.md) · **Français** · [Deutsch](README.de.md) · [Русский](README.ru.md)

Dessinez des prototypes de niveaux modifiables dans **Blender 5+** et exportez-les vers **Godot**. Version **0.8.3**, sous licence **GPL-3.0-or-later**.

Blocksmith est une réalisation indépendante inspirée des méthodes de travail de BlockD décrites publiquement. Il ne reprend pas toutes les fonctions de BlockD. L’interface est disponible en anglais, espagnol, français, allemand et russe. Choisissez la langue dans **Edit → Preferences → Interface → Translation** et activez **Interface** et **Tooltips**. Blocksmith suit la langue de Blender ; les noms des objets existants sont conservés.

## Fonctionnalités

- Dessinez des murs, sols, pièces, escaliers et rampes dans la vue 3D ; choisissez parmi 32 préréglages avec aperçu.
- Modifiez les dimensions dans le panneau latéral ou avec les poignées de la vue. Portes, fenêtres, arches, toitures, garde-corps et murs courbes sont pris en charge.
- Accrochez la géométrie à la grille, aux sommets et aux arêtes visibles, y compris après les modificateurs Boolean et Array. Assemblez les murs droits en onglet, bout à bout ou en T.
- Dessinez des ouvertures non destructives sur des maillages solides et répétez des objets ou ouvertures avec l’outil de rangée.
- Reliez deux niveaux par un escalier droit ou une rampe. Affichez des silhouettes de référence et des indications sur les marches, passages, abris et pentes.
- Appliquez les textures de prototypage Kenney, attribuez des étiquettes de jeu et exportez en GLB ou FBX.
- Marquez des maillages pour permettre leur **placement libre**, sans les contraintes géométriques de Blocksmith.
- Générez des niveaux à partir de JSON validé grâce à une interface en ligne de commande Python, sans installer le module dans votre session personnelle de Blender.

## Installation

1. Téléchargez `blocksmith-0.8.3.zip` depuis les [versions publiées](https://github.com/hlophlopgaming/Blocksmith/releases), ou créez l’archive depuis la racine du dépôt :

   ```sh
   python3 tools/package.py
   ```

2. Dans Blender, ouvrez **Edit → Preferences → Get Extensions → menu en haut à droite → Install from Disk**. Sélectionnez le ZIP téléchargé ou `dist/blocksmith-0.8.3.zip`, puis activez l’extension.
3. Dans la vue 3D, appuyez sur **N** et ouvrez l’onglet **Blocksmith**.

La création de l’archive nécessite Python 3.10+, sans dépendance Python externe. Les archives automatiques **Source code** de GitHub contiennent les sources ; ce ne sont pas des archives d’installation de l’extension.

## Premiers pas

1. Cliquez sur **Dessiner des structures**, ou appuyez sur **Maj+Alt+D**.
2. Choisissez une forme dans la rangée supérieure ou dans **Structure suivante**. **Catalogue de préréglages** ouvre le catalogue de préréglages.
3. Faites glisser le bouton gauche, puis relâchez pour créer la structure. Sélectionnez-la pour modifier ses dimensions ou utiliser les poignées orange.
4. Activez **Répéter** pour continuer à dessiner. **Échap / clic droit** annule le geste en cours ou revient à la sélection.

Pendant le dessin ordinaire, **Ctrl** désactive temporairement l’accrochage, **Maj** contraint la direction par pas de 45° ou crée une base carrée, **H** règle la hauteur et **F** inverse les escaliers ou rampes. Entre les gestes, la navigation et les commandes du panneau restent disponibles.

Pour un escalier droit ou une rampe, tracez du sol inférieur au bord de la plateforme supérieure ; le geste inverse fonctionne aussi. Pour une porte, une fenêtre ou une arche, tracez un rectangle sur un maillage solide : chaque ouverture ajoute une découpe Boolean non destructive. Les murs courbes utilisent des points, un tracé à main levée ou un arc à trois points. Le [manuel détaillé en russe](manual.ru.md) décrit les commandes propres aux outils avancés.

## Placement libre

Sélectionnez un maillage et activez **N → Blocksmith → Ignorer les règles de Blocksmith**. C’est une propriété persistante de l’objet, disponible dans les modes Objet et Édition. Pour plusieurs maillages sélectionnés, utilisez **Appliquer à la sélection** après avoir activé la propriété du maillage actif.

Les maillages marqués peuvent chevaucher d’autres objets, être déplacés, tournés, redimensionnés, utiliser une échelle négative et subir des modifications manuelles ou une inversion des normales sans annulation par Blocksmith. Les autres modules peuvent aussi chevaucher un maillage marqué. La marque ne modifie ni géométrie, ni matériaux, ni étiquettes de jeu. Elle est conservée lors de la duplication, de la conversion en maillage et de l’enregistrement ou du chargement d’un `.blend`. Le maillage reste utilisable pour l’accrochage et l’export, sauf si son rôle l’exclut déjà, comme un objet de découpe ou une silhouette de référence.

Désactiver la propriété rétablit la protection habituelle du module. Si son état actuel enfreint les règles, la protection reste désactivée : le maillage et ses retouches sont conservés. Corrigez d’abord ses intersections, son échelle ou ses normales. Les maillages ordinaires de Blender ne sont pas contraints, même sans cette marque. L’opération prend en charge l’annulation et le rétablissement.

Pour les scripts, sélectionnez les maillages et exécutez :

```python
obj.bs.free_placement = True
bpy.ops.blocksmith.free_placement(enabled=True)
bpy.ops.blocksmith.free_placement(enabled=False)
```

La marque contourne la validation : une géométrie marquée peut être exportée avec des intersections ou des défauts. L’accrochage de Blender et les indications de dimensions restent des réglages distincts. Une transformation du parent peut encore être refusée si elle affecte un enfant protégé.

## Protection de la géométrie

Les modules Blocksmith non marqués refusent les intersections, les échelles négatives ou nulles, les maillages ouverts et les normales inversées. Le contact entre faces est autorisé. Les contrôles utilisent la géométrie évaluée, et pas seulement les boîtes englobantes. Les maillages ordinaires ou importés, les références, l’eau et les objets de découpe Boolean actifs sont exclus de ces contrôles de solides.

La protection couvre les opérations du module, les transformations natives, les modifications après la sortie du mode Édition et l’annulation/rétablissement. L’export valide à nouveau les modules protégés. Les scènes existantes sont acceptées comme état initial sans suppression d’objets, mais les conflits entre modules protégés doivent être corrigés avant l’export. Ces contrôles numériques peuvent être plus lents dans les scènes complexes et ne constituent pas une garantie mathématique.

## Export vers Godot

Ouvrez **Exporter vers Godot**, choisissez **GLB** ou **FBX**, les objets à exporter, le dossier et le nom de fichier. Enregistrez le `.blend` avant d’utiliser un chemin relatif.

GLB est le format principal testé. Avec les collisions activées, les maillages solides reçoivent le suffixe Godot `-col`. L’eau est exportée visiblement, sans collision. Les références, les objets de découpe utilisés, les archives masquées des maillages sources et les objets temporaires de protection sont exclus. Les murs courbes sont convertis en maillages. Les fichiers existants ne sont pas écrasés : choisissez un autre nom ou dossier.

## Ligne de commande JSON

Depuis la racine du dépôt, avec Python 3.10+ et Blender 5+ dans `PATH` :

```sh
python3 tools/levelgen.py shapes
python3 tools/levelgen.py presets
python3 tools/levelgen.py schema
python3 tools/levelgen.py validate examples/courtyard.json
python3 tools/levelgen.py generate examples/courtyard.json --out-dir generated/courtyard
```

La génération produit `level.blend`, `level.glb`, `level.spec.json`, `report.json` et `blender.log`. Utilisez `--blender /chemin/vers/blender` pour choisir un autre exécutable et `--overwrite` pour remplacer les résultats précédents. Blender s’exécute dans un processus séparé en arrière-plan ; un échec de validation préserve les exports précédents. La sortie est au format JSON ; les erreurs utilisent stderr et un code de sortie non nul.

La spécification utilise des **mètres**, les coordonnées Blender avec **Z vers le haut** et des angles d’Euler en **degrés**. GLB convertit les coordonnées vers l’axe Y vertical de Godot. Consultez le [schéma](../examples/level.schema.json), les [exemples](../examples/) et la commande `schema`. Les clés inconnues, noms dupliqués, nombres invalides et complexités excessives sont refusés ; JSON n’exécute jamais de Python. La marque de placement libre est un réglage du maillage dans Blender, pas un champ du schéma CLI actuel.

## Développement et vérifications

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/free_placement_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/guard_check.py
python3 tools/package.py
```

Consultez [CONTRIBUTING](../CONTRIBUTING.md), [CHANGELOG](../CHANGELOG.md) et le [rapport de validation 0.8.3](validation-0.8.3.md), actuellement en russe. GitHub Actions est configuré pour exécuter les tests Python, vérifier la syntaxe et créer l’archive. Les tests de la vue 3D nécessitent un environnement graphique. Les sauvegardes, archives de compilation et scènes générées sont exclues de Git.

## Limites actuelles

Blender 5.0 est le minimum déclaré, mais n’a pas été testé séparément. Les vérifications antérieures portaient sur Blender 5.2.3, 5.3.0 et Godot 4.7.2. FBX est moins testé que GLB. Les chaînes de murs ne se ferment pas automatiquement et ne déplacent pas les murs voisins lorsqu’un mur est modifié. Utilisez **Maj+D** pour des copies modifiables indépendamment ; **Alt+D** partage le maillage, mais pas ses paramètres. Apply Scale accepte une échelle positive uniforme sur un maillage paramétrique non modifié et à utilisateur unique. Les indications ne simulent pas un contrôleur de jeu. Les collisions exportées sont des maillages triangulés statiques. Les maillages de prototypage peuvent nécessiter une optimisation pour la production.

## Licence

Code de Blocksmith : **GPL-3.0-or-later**, voir [LICENSE](../LICENSE). Une copie est incluse dans l’archive d’installation.

[Kenney Prototype Textures](https://kenney.nl/assets/prototype-textures) : **CC0**. Leur [licence](../blocksmith/assets/kenney/License.txt) et leurs [informations de provenance](../blocksmith/assets/kenney/SOURCE.txt) sont conservées avec les ressources.
