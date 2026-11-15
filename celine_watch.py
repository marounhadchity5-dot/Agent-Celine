#!/usr/bin/env python3
"""
Agent de surveillance des billets Céline Dion (Paris La Défense Arena, mai 2027).

À chaque exécution :
  1. ouvre chaque page listée dans sites.json avec un vrai navigateur (Chromium) ;
  2. repère les lignes qui contiennent un prix (offres de billets) ;
  3. compare avec la vérification précédente (fichier state.json) ;
  4. envoie UN email Gmail s'il y a de nouvelles offres, si un site se met à
     bloquer l'agent (ou se débloque), et un petit bilan chaque lundi.

Variables d'environnement (secrets GitHub) :
  GMAIL_ADDRESS       votre adresse Gmail (expéditeur)
  GMAIL_APP_PASSWORD  mot de passe d'application Gmail (16 caractères)
  ALERT_TO            (facultatif) destinataire, sinon GMAIL_ADDRESS
  DRY_RUN=1           (facultatif) n'envoie pas d'email, affiche seulement
"""

import hashlib
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_FILE = Path(os.environ.get("CONFIG_FILE", HERE / "sites.json"))
STATE_FILE = Path(os.environ.get("STATE_FILE", HERE / "state.json"))
PARIS = timezone(timedelta(hours=1))  # heure de Paris (approx., suffisant pour l'affichage)

# --- Détection ---------------------------------------------------------------

PRICE_RE = re.compile(
    r"(?:(?:€|EUR|£|\$|US\$)\s?\d[\d\s  .,]*\d|\d[\d\s  .,]*\s?(?:€|EUR|£))",
    re.IGNORECASE,
)
BLOCK_HINTS = [
    "captcha", "access denied", "accès refusé", "pardon our interruption",
    "verify you are human", "vérifiez que vous êtes humain", "just a moment",
    "unusual traffic", "trafic inhabituel", "are you a robot", "êtes-vous un robot",
    "request unsuccessful", "incapsula", "datadome", "px-captcha", "cf-chl",
]
NO_TICKET_HINTS = [
    "aucun billet", "pas de billet", "plus de billets", "aucune offre",
    "no tickets", "no listings", "sold out", "épuisé", "complet",
    "aucun résultat", "no results",
]
RELEVANT_HINTS = ["celine", "céline", "dion", "2027", "mai", "may", "défense", "defense", "plenitude", "plénitude"]


def normalize(line: str) -> str:
    line = line.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", line).strip()


def price_value(text: str):
    """Renvoie le premier montant trouvé dans la ligne (float) ou None."""
    m = PRICE_RE.search(text)
    if not m:
        return None
    digits = re.sub(r"[^\d,.]", "", m.group(0))
    if not digits:
        return None
    # "1.234,50" / "1,234.50" / "234,50" / "1 234"
    if "," in digits and "." in digits:
        if digits.rfind(",") > digits.rfind("."):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
    elif "," in digits:
        head, _, tail = digits.rpartition(",")
        digits = head.replace(",", "") + ("." + tail if len(tail) == 2 else tail)
    elif digits.count(".") >= 1:
        head, _, tail = digits.rpartition(".")
        digits = head.replace(".", "") + ("." + tail if len(tail) == 2 else tail)
    try:
        return float(digits)
    except ValueError:
        return None


def analyse_page(text: str, html: str, status, filtres: dict) -> dict:
    low = text.lower()
    html_low = (html or "").lower()
    blocked = bool(status and status in (401, 403, 429, 503)) or any(
        h in low or h in html_low[:20000] for h in BLOCK_HINTS
    )
    # Une page quasi vide avec un défi JS est aussi un blocage
    if len(low.strip()) < 80 and ("challenge" in html_low or "captcha" in html_low):
        blocked = True

    lines = [normalize(l) for l in text.splitlines()]
    offers = []
    for i, line in enumerate(lines):
        if not line or len(line) > 220 or not PRICE_RE.search(line):
            continue
        # contexte : la ligne + les 3 lignes au-dessus (date, catégorie, nb de billets)
        context = " | ".join(x for x in lines[max(0, i - 3): i + 1] if x)[:300]
        value = price_value(line)
        pmax = filtres.get("prix_max_euros")
        if pmax is not None and value is not None and value > pmax:
            continue
        mots = [m.lower() for m in filtres.get("mots_cles_obligatoires") or []]
        if mots and not all(m in context.lower() for m in mots):
            continue
        offers.append(context)

    # dédoublonnage en gardant l'ordre
    seen, unique = set(), []
    for o in offers:
        if o not in seen:
            seen.add(o)
            unique.append(o)

    return {
        "blocked": blocked,
        "status": status,
        "no_ticket_message": any(h in low for h in NO_TICKET_HINTS),
        "mentions_celine": any(h in low for h in RELEVANT_HINTS[:3]),
        "offers": unique[:80],
    }


# --- Navigation --------------------------------------------------------------

def fetch_all(sites):
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        for site in sites:
            name = site["nom"]
            page = context.new_page()
            try:
                resp = page.goto(site["url"], wait_until="domcontentloaded", timeout=45000)
                status = resp.status if resp else None
                page.wait_for_timeout(6000)
                # accepte les cookies si un bouton évident est présent
                for label in ["Tout accepter", "Accepter", "J'accepte", "Accept all", "Accept"]:
                    try:
                        btn = page.get_by_role("button", name=label, exact=False).first
                        if btn.is_visible(timeout=500):
                            btn.click(timeout=1500)
                            page.wait_for_timeout(1500)
                            break
                    except Exception:
                        pass
                for _ in range(4):  # fait défiler pour charger les listes
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(1200)
                text = page.inner_text("body", timeout=15000)
                html = page.content()
                results[name] = {"ok": True, "status": status, "text": text, "html": html,
                                 "final_url": page.url}
            except Exception as e:  # noqa: BLE001
                results[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
            finally:
                page.close()
        browser.close()
    return results


# --- Email -------------------------------------------------------------------

def send_email(subject: str, body: str):
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = os.environ.get("ALERT_TO", "").strip() or sender
    if os.environ.get("DRY_RUN") == "1" or not sender or not password:
        print("\n===== EMAIL (non envoyé : DRY_RUN ou identifiants absents) =====")
        print("Objet :", subject)
        print(body)
        print("===============================================================\n")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"Agent Céline Dion <{sender}>"
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(sender, password)
        s.sendmail(sender, [to], msg.as_string())
    print(f"Email envoyé à {to} : {subject}")


# --- Programme principal -----------------------------------------------------

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def offer_key(o: str) -> str:
    return hashlib.sha1(o.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    config = load_json(CONFIG_FILE, {})
    sites = [s for s in config.get("sites", []) if s.get("actif", True)]
    filtres = config.get("filtres", {}) or {}
    state = load_json(STATE_FILE, {"sites": {}})
    state.setdefault("sites", {})
    first_run = not state["sites"]
    now = datetime.now(PARIS)

    raw = fetch_all(sites)

    new_offers_section, status_changes, summary_lines = [], [], []

    for site in sites:
        name, url = site["nom"], site["url"]
        prev = state["sites"].get(name, {})
        r = raw.get(name, {"ok": False, "error": "pas de résultat"})

        if not r.get("ok"):
            status = "erreur"
            detail = r.get("error", "")
            analysis = None
        else:
            analysis = analyse_page(r["text"], r["html"], r["status"], filtres)
            status = "bloqué" if analysis["blocked"] else "ok"
            detail = f"HTTP {r['status']}"

        # changements d'état (bloqué / débloqué / erreur)
        prev_status = prev.get("status")
        if prev_status and prev_status != status:
            if status == "ok":
                status_changes.append(f"✅ {name} : l'agent a de nouveau accès au site.")
            elif status == "bloqué":
                status_changes.append(
                    f"⚠️ {name} : le site bloque l'agent (protection anti-robot, {detail}). "
                    f"Vérifiez à la main : {url}"
                )
            else:
                status_changes.append(f"⚠️ {name} : erreur de chargement ({detail}).")
        elif first_run and status != "ok":
            status_changes.append(f"⚠️ {name} : {status} dès la 1re vérification ({detail}). {url}")

        known = set(prev.get("offer_keys", []))
        offers = analysis["offers"] if (analysis and status == "ok") else []
        keys = [offer_key(o) for o in offers]
        fresh = [o for o, k in zip(offers, keys) if k not in known]

        if status == "ok" and fresh and not first_run:
            tag = "" if site.get("officiel") else "  (site NON officiel : risque d'arnaque, vérifiez bien)"
            block = [f"▶ {name}{tag}", f"   {r.get('final_url', url)}"]
            for o in fresh[:15]:
                block.append(f"   • {o}")
            if len(fresh) > 15:
                block.append(f"   … et {len(fresh) - 15} autre(s)")
            new_offers_section.append("\n".join(block))

        summary_lines.append(
            f"- {name} : {status}"
            + (f", {len(offers)} ligne(s) avec prix" if status == "ok" else "")
            + (", message « aucun billet » affiché" if analysis and analysis["no_ticket_message"] else "")
        )

        # on garde les offres déjà vues (bornées) ; si le site est bloqué on conserve l'ancien état
        if status == "ok":
            merged = list(dict.fromkeys(keys + prev.get("offer_keys", [])))[:400]
        else:
            merged = prev.get("offer_keys", [])
        state["sites"][name] = {
            "status": status,
            "offer_keys": merged,
        }

    stamp = now.strftime("%d/%m/%Y %H:%M")
    footer = (
        "\n\n— Agent Céline Dion (GitHub Actions)\n"
        "Achetez de préférence via AXS, Ticketmaster, Fnac Spectacles ou Paris La Défense Arena."
    )

    if first_run:
        send_email(
            "🎤 Agent Céline Dion activé",
            f"L'agent est en place ({stamp}). Il vérifie les sites régulièrement et vous écrit "
            f"dès qu'une nouvelle offre apparaît.\n\nÉtat de départ :\n" + "\n".join(summary_lines)
            + ("\n\n" + "\n".join(status_changes) if status_changes else "") + footer,
        )
    else:
        if new_offers_section:
            send_email(
                f"🎟️ Céline Dion : nouvelle(s) offre(s) détectée(s) – {stamp}",
                "De nouvelles lignes avec un prix sont apparues :\n\n"
                + "\n\n".join(new_offers_section)
                + ("\n\nÀ noter :\n" + "\n".join(status_changes) if status_changes else "")
                + footer,
            )
        elif status_changes:
            send_email(f"ℹ️ Agent Céline Dion : changement d'accès – {stamp}",
                       "\n".join(status_changes) + footer)

        # petit bilan hebdomadaire (lundi, une fois)
        week = now.strftime("%G-W%V")
        if now.weekday() == 0 and state.get("last_weekly") != week:
            send_email(f"📋 Agent Céline Dion : bilan de la semaine – {stamp}",
                       "L'agent fonctionne. État actuel :\n" + "\n".join(summary_lines) + footer)
            state["last_weekly"] = week

    state["last_run_day"] = now.strftime("%Y-%m-%d")
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(summary_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
