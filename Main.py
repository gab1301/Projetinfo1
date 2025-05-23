# 🚀 Script Streamlit Détection de Bots Facebook - Mise à jour des sélecteurs HTML (commentaires)

import time
import csv
import random
import streamlit as st
from playwright.sync_api import sync_playwright
from fuzzywuzzy import fuzz
from collections import defaultdict
import os

NB_MAX_POSTS = 200
STATE_FILE = "state.json"
SIMILARITY_THRESHOLD = 98

def scroll_to_load_posts(page, max_scrolls=100):
    for _ in range(max_scrolls):
        page.keyboard.press("PageDown")
        time.sleep(2.5)

def get_filtered_post_links(page, keywords=[], min_comments=10, debug=False):
    scroll_to_load_posts(page)
    post_links = []
    links_seen = set()
    posts = page.query_selector_all("a[href*='/posts/']")
    total_checked = 0
    total_ignored = 0

    for post in posts:
        if len(post_links) >= NB_MAX_POSTS:
            break
        try:
            href = post.get_attribute("href")
        except:
            continue

        if href and href not in links_seen:
            full_link = "https://www.facebook.com" + href if "facebook.com" not in href else href
            links_seen.add(href)
            try:
                page.goto(full_link)
                time.sleep(random.uniform(3, 5))
            except:
                continue
            total_checked += 1

            try:
                comment_text = page.inner_text("span[aria-label*='commentaire']")
                comment_count = int(''.join(filter(str.isdigit, comment_text)))
                if comment_count >= min_comments:
                    post_links.append(full_link)
                else:
                    total_ignored += 1
            except:
                total_ignored += 1

    if debug:
        st.info(f"🔍 {total_checked} post(s) vérifié(s), {len(post_links)} retenu(s), {total_ignored} ignoré(s)")

    return post_links

def scroll_and_expand_comments(page):
    for _ in range(7):
        page.keyboard.press("PageDown")
        time.sleep(1.5)
        try:
            more_buttons = page.query_selector_all("text='Voir plus de commentaires'")
            for btn in more_buttons:
                try:
                    btn.click()
                    time.sleep(1.2)
                except:
                    continue
        except:
            pass

def get_comments(page, debug=False):
    scroll_and_expand_comments(page)
    comments = []
    try:
        # Essai avec un sélecteur plus générique pour les commentaires
        comment_elements = page.query_selector_all("div[role='article'] div[dir='auto']")
        for c in comment_elements:
            try:
                text = c.inner_text()
                if len(text.strip()) > 10 and not text.startswith("J’aime"):
                    parent = c.evaluate_handle("node => node.closest('[role=\"article\"]')")
                    user_el = parent.query_selector("h3") if parent else None
                    user = user_el.inner_text() if user_el else "Inconnu"
                    comments.append((text.strip(), user.strip()))
            except:
                continue
        if debug:
            st.write(f"💬 {len(comments)} commentaire(s) récupéré(s)")
    except:
        pass

    if debug and comments:
        comments.append((comments[0][0], "Bot_Test1"))
        comments.append((comments[0][0] + ".", "Bot_Test2"))

    return comments

def detect_bot_comments(comments, threshold=SIMILARITY_THRESHOLD):
    similarities = defaultdict(list)
    for i in range(len(comments)):
        for j in range(i + 1, len(comments)):
            sim = fuzz.ratio(comments[i][0].lower(), comments[j][0].lower())
            if sim >= threshold:
                similarities[comments[i][0]].append(comments[i][1])
                similarities[comments[j][0]].append(comments[j][1])
    return {c: list(set(u)) for c, u in similarities.items() if len(u) > 1}

def save_results_to_csv(bot_comments, filename="bot_comments.csv"):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Commentaire", "Utilisateurs suspects"])
        for comment, users in bot_comments.items():
            writer.writerow([comment, ", ".join(users)])
    return filename

# === Interface Streamlit ===
st.set_page_config(page_title="Détecteur de Bots Facebook", layout="centered")
st.title("🤖 Détecteur de Bots Facebook")

account = st.text_input("Nom de la page Facebook (ex : lemonde.fr)")
keywords_input = st.text_input("Mots-clés (séparés par des virgules) (optionnel, pas utilisé pour filtrer)")
min_comments = st.slider("Nombre minimum de commentaires", 0, 1000, 0)
debug_mode = st.checkbox("🔍 Mode Debug (affiche les textes et les commentaires)")
start = st.button("Lancer l'analyse")

if start and account:
    keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    page_url = f"https://www.facebook.com/{account}"

    with st.spinner("🔄 Analyse en cours, défilement long pour charger les anciennes publications..."):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()

            page.goto(page_url)
            time.sleep(5)

            post_links = get_filtered_post_links(page, keywords, min_comments, debug=debug_mode)
            st.write(f"🔗 {len(post_links)} post(s) sélectionné(s)")

            all_comments = []
            for link in post_links:
                page.goto(link)
                time.sleep(random.uniform(2.5, 4))
                comments = get_comments(page, debug=debug_mode)
                all_comments.extend(comments)

            if not all_comments:
                st.warning("Aucun commentaire récupéré. Vérifie que le post contient bien des commentaires visibles.")

            bots = detect_bot_comments(all_comments)

            if bots:
                st.subheader("🛑 Commentaires suspects détectés")
                for comment, users in bots.items():
                    st.markdown(f"**Commentaire :** {comment}")
                    st.markdown(f"**Utilisateurs :** {', '.join(users)}")
                    st.markdown("---")
                csv_path = save_results_to_csv(bots)
                st.success("Résultats sauvegardés dans 'bot_comments.csv'")

                with open(csv_path, "rb") as f:
                    st.download_button("📥 Télécharger les résultats CSV", f, file_name="bot_comments.csv")
            else:
                st.success("Aucun comportement suspect détecté.")

            browser.close(
