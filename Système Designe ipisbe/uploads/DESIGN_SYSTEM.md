# IPISB Connect — Design System Reference

> Référence officielle du design system. À utiliser pour tout nouveau composant ou page.

---

## Couleurs (OKLCH)

### Palette principale
| Variable | Valeur OKLCH | Usage |
|---|---|---|
| `--pal-ink` | `oklch(22% 0.025 175)` | Texte principal sombre / fond dark mode |
| `--pal-text` | `oklch(34% 0.03 180)` | Corps de texte |
| `--pal-muted` | `oklch(48% 0.02 180)` | Texte secondaire / muted |
| `--pal-primary` | `oklch(48% 0.085 175)` | Couleur brand principale (teal) |
| `--pal-primary-deep` | `oklch(38% 0.07 175)` | Hover du primary |
| `--pal-mid` | `oklch(62% 0.085 170)` | Accent teal clair |
| `--pal-soft` | `oklch(82% 0.045 165)` | Fond doux |
| `--pal-pale` | `oklch(94% 0.025 165)` | Hover states / fonds très clairs |
| `--pal-cream` | `oklch(97% 0.012 90)` | Fond body (blanc chaud) |
| `--pal-paper` | `oklch(99% 0.005 160)` | Blanc pur / fond cartes |
| `--pal-line` | `oklch(88% 0.015 170)` | Bordures |
| `--pal-line-soft` | `oklch(92% 0.012 170)` | Bordures subtiles |

### Couleurs sémantiques
| Variable | Valeur OKLCH | Usage |
|---|---|---|
| `--pal-accent` | `oklch(72% 0.11 60)` | Ambre / jaune accent |
| `--pal-warn` | `oklch(78% 0.12 80)` | Avertissement chaud |
| `--pal-good` | `oklch(70% 0.13 155)` | Succès / vert |
| `--pal-danger` | `oklch(64% 0.18 25)` | Erreur / rouge |

### Tokens Tailwind (mappage)
```
--background   → --pal-paper
--foreground   → --pal-ink
--card         → --pal-paper
--primary      → --pal-primary
--secondary    → --pal-pale
--muted        → --pal-pale
--destructive  → --pal-danger
--border       → --pal-line
--ring         → --pal-mid
```

### Dark Mode (classe `.dark`)
- background → `--pal-ink`
- card → `--pal-ink2` `oklch(28% 0.04 175)`
- foreground → `--pal-paper`
- primary → `--pal-mid` (plus clair pour contraste)
- border → `oklch(1 0 0 / 10%)`

### Gradients
```css
--gradient-brand: linear-gradient(135deg, var(--pal-primary) 0%, var(--pal-mid) 100%)
--gradient-soft:  linear-gradient(135deg, var(--pal-pale) 0%, var(--pal-cream) 100%)
```

---

## Typographie

### Polices
| Rôle | Famille | Poids |
|---|---|---|
| **Display / Titres** | `Cormorant Garamond` (serif) | 400, 500, 600, 700 |
| **Corps / UI** | `Manrope` (sans-serif) | 400, 500, 600, 700, 800 |
| **Code** | `JetBrains Mono` | 400, 600, 700 |

### Échelle typographique
| Élément | Police | Taille | Poids | Interligne |
|---|---|---|---|---|
| Hero H1 | Serif | clamp(64px, 7vw, 96px) | 500 | 0.97 |
| H1–H6 | Serif | variable | variable | tight |
| Body large | Sans | 17px | 400 | 1.6 |
| Body standard | Sans | 13px | 400 | — |
| Eyebrow label | Sans | 10.5–11px | 700 | 1 | UPPERCASE, letter-spacing: 0.18em |
| Stat number | Serif | 38px | 500 | 1 | oldstyle-nums |
| Button | Sans | 13px | 700 | 1 |
| Small / caption | Sans | 12px | 400 | — |

---

## Border Radius

| Token | Valeur | Usage |
|---|---|---|
| `--radius` (base) | `0.625rem` (10px) | Base |
| `--radius-sm` | 6px | Petits éléments |
| `--radius-md` | 8px | Inputs, boutons |
| `--radius-lg` | 10px | Standard |
| `--radius-xl` | 14px | Cartes |
| `--radius-2xl` | 18px | Modales |
| `rounded-full` | 9999px | Pills, badges |

---

## Shadows

```css
--shadow-card:   0 1px 4px oklch(0% 0 0/.06), 0 4px 16px oklch(0% 0 0/.04)
--shadow-card-2: 0 1px 3px oklch(0% 0 0/.05), 0 6px 20px oklch(30% 0.03 175/.06)
--shadow-pop:    0 4px 12px oklch(0% 0 0/.08), 0 16px 48px oklch(30% 0.03 175/.14)
--shadow-glow:   0 0 24px oklch(48% 0.085 175/.25)
```

---

## Boutons

### Variantes
| Variante | Fond | Texte | Hover |
|---|---|---|---|
| `default` | `--pal-primary` | white | `--pal-primary-deep` |
| `outline` | transparent | foreground | pale bg |
| `secondary` | `--pal-pale` | foreground | légèrement plus sombre |
| `ghost` | transparent | foreground | muted bg |
| `destructive` | `--pal-danger/10` | `--pal-danger` | danger plein |
| `link` | transparent | primary | underline |

### Tailles
| Size | Hauteur | Padding | Fonte |
|---|---|---|---|
| `xs` | 24px | px-2 | 12px |
| `sm` | 28px | px-2.5 | 12.8px |
| `default` | 32px | px-2.5 | 14px |
| `lg` | 36px | px-2.5 | 14px |
| `icon` | 32×32px | — | — |

### Classes custom
```
.btn-c-primary  → bg ink, hover primary-deep
.btn-c-green    → bg primary, hover primary-deep
.btn-c-ghost    → transparent + border-line, hover pale
.btn-c-soft     → bg pale, text primary-deep
.btn-c-danger   → bg danger
```

---

## Cartes

```
rounded-xl (14px)
ring-1 ring-foreground/10
bg-card
gap-4 (vertical)
padding: py-4 px-4
```

**Classe custom `.dash-card`**
```
bg-pal-paper
border: 1px pal-line-soft
border-radius: 16px
shadow: --shadow-card-2
```

---

## Inputs

```
height: 32px
padding: 9px 13px
border-radius: rounded-lg (8px)
border: --pal-line
focus: box-shadow 0 0 0 3px pal-pale
font-size: 13px
```

---

## Badges / Chips

### Badges (shadcn)
```
height: 20px
padding: px-2 py-0.5
border-radius: rounded-full (pill)
font-size: 12px, font-weight: 500
```

### Chips custom (`.chip-c`)
```
font-size: 11px
border-radius: 10px
padding: 3px 10px
```
| Variante | Fond | Texte |
|---|---|---|
| `.chip-c-green` | `--pal-pale` | `--pal-primary-deep` |
| `.chip-c-amber` | `oklch(95% 0.04 80)` | `oklch(50% 0.1 70)` |
| `.chip-c-red` | `oklch(95% 0.03 25)` | `oklch(50% 0.15 25)` |
| `.chip-c-blue` | `oklch(94% 0.03 250)` | `oklch(40% 0.09 250)` |

---

## Animations

```css
@keyframes rise     { from: opacity:0, translateY(18px) → to: opacity:1, Y(0) }
@keyframes pop-in   { from: opacity:0, translateY(10px) scale(.97) → to: visible }
@keyframes fade-in  { from: opacity:0 → to: opacity:1 }
```

| Classe | Durée | Effet |
|---|---|---|
| `.anim-rise` | 0.6s | Montée + apparition |
| `.anim-pop` | 0.28s | Pop-in scale |
| `.anim-fade` | 0.22s | Fade simple |
| `.page-enter` | 0.4s | Transition de route |

**Easing custom** : `cubic-bezier(.22,1,.36,1)`

---

## Navigation sidebar

```
Largeur étendue : 256px
Largeur réduite : 48px (icônes)
Mobile : 288px
```

**Lien sidebar `.side-link`**
```
padding: 9px 12px
border-radius: 10px
font-size: 13.5px
normal: text-muted
hover: bg-pale, text-ink
active: bg-pale, text-primary-deep, font-bold, barre gauche 3px primary
```

---

## Utilitaires interactifs

```
.u-hover-lift   → lift -2px Y + shadow au hover, scale(0.98) active
.u-card-lift    → lift -3px Y au hover (cartes)
.u-ghost        → hover bg-pale
.u-input        → focus ring override
.scroll-y       → scrollbar fin custom (8px, couleur pal-soft)
```

---

## Accessibilité

```css
:focus-visible {
  outline: 2px solid var(--pal-mid);
  outline-offset: 2px;
  border-radius: 4px;
}
@media (prefers-reduced-motion: reduce) {
  /* toutes animations désactivées */
}
```

---

## Stack technique

| Outil | Usage |
|---|---|
| Tailwind CSS v4 | Utilitaires CSS |
| shadcn/ui | Composants de base |
| Radix UI | Primitives accessibles |
| CVA | Variantes de composants |
| clsx + tailwind-merge | Composition de classes |
| lucide-react | Icônes |
| Framer Motion | Animations complexes |
| next-themes | Dark/light mode |
