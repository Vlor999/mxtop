# mxtop - Documentation Fonctionnelle

## Description

mxtop est un outil de monitoring de performance en temps réel pour les Mac équipés de puces Apple Silicon (M1, M2, M3, M4, M5 et leurs variantes Pro, Max, Ultra). Il affiche dans le terminal un tableau de bord complet avec l'utilisation CPU, GPU, la consommation électrique, la mémoire, les informations système et le débit réseau.

## Configuration requise

- macOS (Apple Silicon uniquement : M1 à M5 et variantes)
- Python 3.11 ou supérieur
- Droits sudo (requis pour les métriques complètes via `powermetrics`)

## Installation

```bash
pip install mxtop
```

Ou depuis les sources :
```bash
git clone https://github.com/Vlor999/mxtop.git
cd mxtop
uv sync
```

## Utilisation

### Lancement

```bash
sudo mxtop
```

> **Note** : `sudo` est requis pour accéder à `powermetrics`. Sans `sudo`, les métriques de puissance CPU/GPU/ANE et la pression thermique ne sont pas disponibles.

### Quitter

Appuyez sur **q**, **Q** ou **ESC** pour quitter proprement.

## Métriques affichées

### 1. Processeur (CPU)

Les labels des clusters sont **dynamiques** selon la génération de puce :

| Génération | Jauge 1 (efficacité) | Jauge 2 (performance) |
|---|---|---|
| M1 – M4 | `E-CPU` | `P-CPU` |
| M5 Pro/Max | `P-CPU` (12 cœurs) | `S-CPU` (6 super cœurs) |

Chaque jauge affiche :
- Pourcentage d'utilisation
- Fréquence actuelle (MHz)
- Cœurs individuels (avec `--show_cores`)

**Exemples d'affichage :**
```
# Sur M1–M4
E-CPU Usage: 23% @ 1200 MHz
P-CPU Usage: 65% @ 3504 MHz

# Sur M5 Pro
P-CPU Usage: 18% @ 1200 MHz
S-CPU Usage: 72% @ 4500 MHz
```

### 2. GPU

- Pourcentage d'utilisation
- Fréquence actuelle (MHz)

```
GPU Usage: 12% @ 1398 MHz
```

### 3. ANE (Apple Neural Engine)

- Estimation de l'utilisation basée sur la puissance consommée rapportée à la puissance maximale de la puce
- Puissance en watts

```
ANE Usage: 5% @ 0.4 W
```

### 4. Mémoire (RAM)

- RAM utilisée / totale (en Go)
- Swap utilisé / total (ou "swap inactive" si non activé)

```
RAM Usage: 12.3/16.0 GB — swap: 0.5/2.0 GB
```

### 5. Graphiques de puissance

Deux graphiques en temps réel montrant la consommation électrique :

**CPU Power :**
- Puissance instantanée (W)
- Puissance moyenne glissante (W)
- Puissance pic (W)

**GPU Power :**
- Puissance instantanée (W)
- Puissance moyenne glissante (W)
- Puissance pic (W)

**Titre du panneau :**
```
CPU+GPU+ANE Power: 15.23 W (avg: 12.50 W  peak: 28.10 W)  throttle: no
```

L'indicateur `throttle: yes/no` indique si le Mac est en throttling thermique.

### 6. WiFi

- Nom du réseau (SSID)
- Force du signal (dBm et pourcentage, plage −90 dBm = 0% / −30 dBm = 100%)
- Débit de transmission (Mbps)

```
WiFi: MonReseau  -52 dBm (63%)  780 Mbps
```

### 7. Batterie

- Niveau de charge (%)
- État : Charging / Charged / Discharging
- Temps restant (si disponible)

```
Battery: 85% (Charging) — 1:23 remaining
```

Sur Mac de bureau (Mac Mini, Mac Studio, Mac Pro) : `Battery: N/A (Desktop Mac)`.

### 8. Chargeur

- Nom de l'adaptateur
- Puissance (W)
- État de la connexion

```
Charger: Apple 140W USB-C Power Adapter (140W) — cable connected
```

### 9. Réseau (I/O)

- Débit montant (upload)
- Débit descendant (download)

```
Network: ↑ 1.2 MB/s  ↓ 15.3 MB/s
```

## Options de ligne de commande

### Intervalle de rafraîchissement

```bash
sudo mxtop --interval 2
```

Rafraîchit l'affichage toutes les 2 secondes au lieu de chaque seconde.

### Couleur

```bash
sudo mxtop --color 5
```

Change la couleur des jauges et graphiques (valeurs 0 à 8).

### Période de moyenne

```bash
sudo mxtop --avg 60
```

Calcule les moyennes de puissance sur les 60 dernières secondes (au lieu de 30).

### Affichage par cœur

```bash
sudo mxtop --show_cores True
```

Affiche une jauge verticale pour chaque cœur CPU individuel, en plus des jauges de cluster. Les cœurs supplémentaires au-delà des slots disponibles sont ignorés sans erreur.

### Relance périodique de powermetrics

```bash
sudo mxtop --max_count 100
```

Relance le processus `powermetrics` tous les 100 échantillons. Utile pour éviter une éventuelle dégradation sur de longues sessions.

### Niveau de log

```bash
sudo mxtop --log-level DEBUG
```

Augmente la verbosité des logs pour le débogage.

## Limitations connues

- **macOS uniquement** : Ne fonctionne que sur macOS avec Apple Silicon
- **sudo requis** : Sans `sudo`, les métriques de puissance (CPU/GPU/ANE watts) et la pression thermique ne sont pas disponibles
- **Précision ANE** : L'utilisation de l'ANE est estimée à partir de la puissance consommée rapportée à la puissance maximale de la puce (valeurs dans `_SOC_SPECS`), pas d'un compteur d'utilisation direct
- **GPU absent** : Sur certaines configurations, le GPU peut ne pas apparaître dans le plist `powermetrics` ; les jauges affichent alors 0%
- **Affichage** : La taille du terminal doit être suffisante pour afficher tous les widgets ; un terminal trop petit peut causer des artefacts visuels
- **Fichiers temporaires** : L'outil écrit dans `/tmp/mxtop_powermetrics*` ; ces fichiers sont nettoyés à la sortie, mais peuvent rester en cas de crash
- **Terminal Ghostty** : L'UI peut être dégradée avec le terminal Ghostty (`xterm-ghostty` non reconnu par dashing) — issue #5
