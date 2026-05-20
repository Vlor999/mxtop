# mxtop - Documentation Technique

## Vue d'ensemble

mxtop est un outil CLI de monitoring de performance pour Apple Silicon (M1 à M5 et variantes). Il affiche en temps réel dans le terminal l'utilisation CPU, GPU, ANE, la consommation électrique, la mémoire, le WiFi, la batterie et le débit réseau. Il s'appuie sur `powermetrics` (outil Apple) pour collecter les métriques du SoC et sur `psutil` pour les métriques système.

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Langage | Python 3.11+ |
| Build system | Hatchling |
| UI Terminal | dashing (TUI) |
| Métriques système | psutil |
| Logging | loguru |
| Métriques SoC | powermetrics (outil macOS natif) |
| Gestion de paquets | uv / pip |
| Tests | pytest |

## Architecture

### Structure du projet

```
mxtop/
  mxtop/                    # Package Python principal
    __init__.py              # Version et metadata
    mxtop.py                 # Point d'entrée et boucle principale
    ui.py                    # Construction de l'interface TUI (widgets dashing)
    parsers.py               # Parsing des données powermetrics (plist)
    utils.py                 # Utilitaires (SoC info, RAM, powermetrics process)
    system_info.py           # Collecte de métriques système (WiFi, batterie, réseau)
    updater.py               # Mise à jour des widgets avec les métriques
    keyboard.py              # Listener clavier (arrière-plan)
  tests/                     # Tests unitaires
    __init__.py
    test_mxtop.py
    test_parsers.py
    test_utils.py
    test_system_info.py
    test_updater.py
  images/                    # Captures d'écran
  docs/                      # Documentation
  pyproject.toml             # Configuration du projet et dépendances
  setup.py                   # Compatibilité setuptools
  uv.lock                    # Lockfile uv
```

### Flux de données

```
powermetrics (sudo)  -->  /tmp/mxtop_powermetrics*  -->  parse_powermetrics()
                                                              |
                                                    parse_cpu_metrics()
                                                    parse_gpu_metrics()
                                                    parse_thermal_pressure()
                                                              |
                                                    update_processor_widgets()
                                                    update_power_charts()
                                                              |
BackgroundMetricsCollector  -->  get_wifi_metrics()     -->  update_wifi_widget()
(thread arrière-plan)           get_power_metrics()    -->  update_power_widgets()
                                get_network_throughput() -> update_network_widget()
                                                              |
psutil.virtual_memory()    -->  get_ram_metrics_dict() -->  update_ram_widget()
                                                              |
                                                           ui.display()
```

### Boucle principale (`mxtop.py`)

1. **Initialisation** :
   - Détection du SoC via `sysctl` et `system_profiler` (parallélisé avec ThreadPoolExecutor)
   - Construction de l'UI (widgets dashing)
   - Lancement du processus `powermetrics` en arrière-plan
   - Attente de la première lecture valide

2. **Threads arrière-plan** :
   - `keyboard_listener` : Écoute les touches q/Q/ESC pour quitter
   - `BackgroundMetricsCollector` : Collecte WiFi, batterie et réseau toutes les 5 secondes

3. **Boucle de rendu** :
   - Parse les derniers résultats de powermetrics
   - Met à jour les widgets CPU, GPU, ANE
   - Met à jour RAM, WiFi, batterie, réseau
   - Appelle `ui.display()` pour redessiner le terminal
   - Dort pendant l'intervalle configuré

4. **Nettoyage** :
   - Arrêt du processus powermetrics (avec `wait(timeout=3)` pour éviter les zombies)
   - Suppression des fichiers temporaires
   - Restauration du curseur terminal

### Hiérarchie des clusters CPU (`parsers.py`)

Apple Silicon utilise plusieurs types de cœurs dont la dénomination évolue par génération. L'ordre de performance croissant est : **E < P < S**.

| Génération | Cluster efficacité | Cluster performance |
|---|---|---|
| M1 – M4 | `E-Cluster` | `P-Cluster` |
| M5 Pro/Max | `P-Cluster` | `S-Cluster` |
| Ultra (multi-die) | `E0-Cluster`, `E1-Cluster`… | `P0-Cluster`, `P1-Cluster`… |

Le parser détecte automatiquement les préfixes présents, les classe par rang (`_CLUSTER_RANK = {"E": 0, "P": 1, "S": 2}`), et assigne :
- **Rang le plus bas → slot efficacité** (jauge cpu1, label `e_cluster_label`)
- **Rang le plus haut → slot performance** (jauge cpu2, label `p_cluster_label`)

La fonction `_synthesize_from_names()` agrège les sous-clusters multi-die en valeurs canoniques `E-Cluster_active` / `P-Cluster_active`.

### Parsing powermetrics (`parsers.py` et `utils.py`)

Le processus `powermetrics` écrit des plists binaires (séparés par NUL) dans un fichier temporaire (`/tmp/mxtop_powermetrics<timecode>`).

La fonction `parse_powermetrics()` :
1. Ouvre le fichier en mode lecture-écriture (`O_RDWR`)
2. Lit seulement les derniers 64 KiB (évite la croissance mémoire)
3. Splitte par `\x00` et parse le dernier chunk valide avec `plistlib`
4. Tronque le fichier pour ne garder que le dernier blob valide
5. Retourne `(cpu_metrics, gpu_metrics, thermal_pressure, None, timestamp)` ou `None`

#### Métriques CPU extraites

```python
{
    # Agrégats canoniques (toujours présents après synthèse)
    "E-Cluster_freq_Mhz": 1200,    # Fréquence slot efficacité
    "E-Cluster_active": 45,         # Utilisation slot efficacité (%)
    "P-Cluster_freq_Mhz": 3500,    # Fréquence slot performance
    "P-Cluster_active": 72,         # Utilisation slot performance (%)
    # Labels d'affichage (dépendent de la puce)
    "e_cluster_label": "E-CPU",     # Ex: "P-CPU" sur M5, "E-CPU" sur M1-M4
    "p_cluster_label": "P-CPU",     # Ex: "S-CPU" sur M5, "P-CPU" sur M1-M4
    # Par cœur (préfixe toujours E-Cluster/P-Cluster quel que soit le nom réel)
    "E-Cluster0_active": 50,
    "P-Cluster0_active": 80,
    "e_core": [0, 1, 2, 3],         # IDs des cœurs efficacité
    "p_core": [4, 5, 6, 7, 8, 9],   # IDs des cœurs performance
    # Puissance
    "ane_W": 0.5,
    "cpu_W": 8.2,
    "gpu_W": 3.1,
    "package_W": 12.8
}
```

#### Robustesse du parser

- `parse_thermal_pressure` : retourne `"Nominal"` si la clé est absente du plist
- `parse_cpu_metrics` : utilise `.get()` sur `processor`/`clusters` ; lève `ValueError` si données manquantes (attrapé par l'appelant via `except Exception`)
- `parse_gpu_metrics` : retourne `{"freq_MHz": 0, "active": 0}` si la clé `gpu` est absente (ex. GPU désactivé)

### Base de données SoC (`utils.py`)

Table de référence des puissances maximales par modèle (utilisée pour normaliser les jauges) :

| SoC | CPU max (W) | GPU max (W) | ANE max (W) |
|-----|-------------|-------------|-------------|
| Apple M1 | 20 | 20 | 8 |
| Apple M1 Pro | 30 | 30 | 8 |
| Apple M1 Max | 30 | 60 | 8 |
| Apple M1 Ultra | 60 | 120 | 16 |
| Apple M2 | 25 | 15 | 8 |
| Apple M2 Pro | 30 | 35 | 8 |
| Apple M2 Max | 30 | 60 | 8 |
| Apple M2 Ultra | 60 | 120 | 16 |
| Apple M3 | 25 | 20 | 8 |
| Apple M3 Pro | 30 | 35 | 8 |
| Apple M3 Max | 40 | 60 | 8 |
| Apple M3 Ultra | 80 | 120 | 16 |
| Apple M4 | 25 | 20 | 8 |
| Apple M4 Pro | 30 | 35 | 8 |
| Apple M4 Max | 40 | 60 | 8 |
| Apple M4 Ultra | 80 | 120 | 16 |
| Apple M5 | 25 | 20 | 8 |
| Apple M5 Pro | 35 | 40 | 8 |
| Apple M5 Max | 45 | 70 | 8 |
| Apple M5 Ultra | 90 | 140 | 16 |

Ces valeurs sont exposées dans `soc_info` via `cpu_max_power`, `gpu_max_power` et `ane_max_power`.

### Interface utilisateur (`ui.py`)

L'UI utilise la librairie `dashing` pour afficher des widgets TUI :

**Widgets :**
- `HGauge` : Jauge horizontale (CPU, GPU, RAM, WiFi, batterie)
- `VGauge` : Jauge verticale (cœurs individuels)
- `HChart` : Graphique horizontal avec historique (puissance CPU/GPU), plafonné à 512 points
- `VSplit` / `HSplit` : Conteneurs de layout

**Layout standard :**
```
+----------------------------------------------+
| Processeur (<e_label> | <p_label> | GPU | ANE)|
+----------------------------------------------+
| RAM         | System Info     | Network I/O   |
|             | WiFi            |               |
|             | Battery         |               |
|             | Charger         |               |
+----------------------------------------------+
| CPU Power Chart   | GPU Power Chart           |
+----------------------------------------------+
```

**Layout avec cœurs individuels (`--show_cores`) :**
```
+---------------------------+-------------------+
| <e_label> Gauge           | Memory            |
| [C0][C1][C2][C3]          | System Info | Net |
| <p_label> Gauge           | Power Charts      |
| [C0][C1]...[Cn]           |                   |
| GPU Gauge | ANE Gauge      |                   |
+---------------------------+-------------------+
```

Les gauges par cœur sont bornées aux slots disponibles dans l'UI ; un cœur supplémentaire sans slot est simplement ignoré (pas d'IndexError).

### Collecte système (`system_info.py`)

La classe `BackgroundMetricsCollector` exécute les appels système coûteux dans un thread daemon (cycle 5s).

**WiFi** (`get_wifi_metrics()`) :
1. `wdutil info` (primaire) — lit le driver kernel directement, fonctionne en root, insensible à la locale macOS. Le parser extrait SSID/RSSI depuis la section suivant immédiatement le SSID connecté.
2. `system_profiler SPAirPortDataType -json` avec drop de privilèges (fallback) — pour les exécutions sans sudo.

**Batterie/alimentation** (`get_power_metrics()`) :
1. `pmset -g batt` : Source d'alimentation, pourcentage, état de charge
2. `system_profiler SPPowerDataType` : Détails du chargeur (puissance, nom)

**Réseau** (`get_network_throughput()`) :
- `psutil.net_io_counters()` : Compteurs cumulés bytes envoyés/reçus

### Mise à jour des widgets (`updater.py`)

- `update_processor_widgets()` : CPU (labels dynamiques), GPU, ANE (max power par puce, plafonné à 100%), cœurs individuels bornés
- `update_ram_widget()` : RAM et swap
- `update_power_charts()` : Graphiques de puissance avec moyennes glissantes et pics ; comparaison thermique insensible à la casse
- `update_wifi_widget()` : Signal WiFi (RSSI → pourcentage sur plage −90/−30 dBm)
- `update_power_widgets()` : Batterie et chargeur
- `update_network_widget()` : Débit réseau (bytes/s)

## Installation

```bash
# Avec uv (recommandé)
git clone https://github.com/Vlor999/mxtop.git
cd mxtop
uv sync

# Avec pip
pip install mxtop
```

## Commande

```bash
# Usage basique (nécessite sudo pour powermetrics)
sudo mxtop

# En développement depuis les sources
sudo /path/to/mxtop/.venv/bin/mxtop
```

### Arguments CLI

| Argument | Type | Défaut | Description |
|----------|------|--------|-------------|
| `--interval` | int | 1 | Intervalle de rafraîchissement en secondes |
| `--color` | int | 2 | Couleur d'affichage (0-8) |
| `--avg` | int | 30 | Période pour les moyennes glissantes (secondes) |
| `--show_cores` | bool | False | Affiche l'utilisation par cœur |
| `--max_count` | int | 0 | Nombre max d'échantillons avant relance de powermetrics (0 = illimité) |
| `--log-level` | str | WARNING | Niveau de log loguru (DEBUG, INFO, WARNING, ERROR) |

## Tests

```bash
pytest          # ou : uv run pytest
```

Les tests couvrent :
- `test_parsers.py` : Parsing des métriques CPU et GPU
- `test_utils.py` : Détection du SoC, métriques RAM
- `test_system_info.py` : Métriques WiFi, batterie, réseau
- `test_updater.py` : Mise à jour des widgets
- `test_mxtop.py` : Tests d'intégration
