import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Deep-link depuis une notification : le `link` porte `?focus=<id>` et on veut
 * amener l'utilisateur sur la ligne/carte exacte de cette entité.
 *
 * - `focusId`   : l'id ciblé (lu une fois depuis l'URL), remis à `null` après le
 *                 pulse ou après `clearFocus()`.
 * - `attachFocus` : ref-callback à poser sur la ligne ciblée. Elle est invoquée
 *                 quand la ligne est réellement montée (souvent après un
 *                 chargement asynchrone) → défilement + pulse, puis nettoyage de
 *                 l'URL.
 * - `clearFocus` : pour les surfaces à modale (page Tâches) qui consomment
 *                 `focusId` elles-mêmes.
 *
 * Lecture ET nettoyage passent tous les deux par l'URL brute
 * (`window.location`/`history.replaceState`), volontairement indépendants du
 * `validateSearch` de chaque route — chaque route ne déclare que les clés
 * qu'elle connaît (ex. `tab`/`scope` pour Comptabilité) et `focus` en serait
 * sinon évincé avant même d'atteindre ce hook.
 */
export function useDeepLinkFocus() {
  const [focusId, setFocusId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("focus");
  });
  const started = useRef(false);

  const clearFocus = useCallback(() => {
    setFocusId(null);
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (!url.searchParams.has("focus")) return;
    url.searchParams.delete("focus");
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }, []);

  const attachFocus = useCallback((el: HTMLElement | null) => {
    if (!el || started.current) return;
    started.current = true;
    el.classList.add("deep-link-focus");
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => { el.classList.remove("deep-link-focus"); setFocusId(null); }, 3000);
    window.setTimeout(clearFocus, 1500);
  }, [clearFocus]);

  return { focusId, attachFocus, clearFocus };
}

/**
 * Variante « modale » : ouvre directement le détail d'une entité présente dans
 * `ids` dès que le `?focus=` correspond, puis nettoie l'URL.
 */
export function useDeepLinkModal(ids: string[], open: (id: string) => void) {
  const { focusId, clearFocus } = useDeepLinkFocus();
  const done = useRef(false);
  useEffect(() => {
    if (done.current || !focusId) return;
    if (!ids.includes(focusId)) return;
    done.current = true;
    open(focusId);
    clearFocus();
  }, [focusId, ids, open, clearFocus]);
}
