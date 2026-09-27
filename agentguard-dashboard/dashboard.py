"""
Dashboard de supervision AgentGuard.
Interroge l'API d'AgentGuard (pas la base de données directement) pour
pouvoir fonctionner même quand les services sont déployés séparément.
"""

import os
import streamlit as st
import httpx

AGENTGUARD_URL = os.environ.get("AGENTGUARD_URL", "http://localhost:8000")

st.set_page_config(page_title="AgentGuard Dashboard", layout="wide")
st.title("🛡️ AgentGuard — Supervision de l'agent")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Sessions récentes")
    try:
        sessions = httpx.get(f"{AGENTGUARD_URL}/sessions", timeout=10).json()
    except Exception as e:
        st.error(f"Impossible de contacter AgentGuard : {e}")
        sessions = []

    status_icons = {"ok": "✅", "alerte": "🟠", "bloque": "🛑", "erreur": "⚠️", "en_cours": "⏳"}

    selected_session_id = None
    for s in sessions:
        icon = status_icons.get(s["status"], "•")
        label = f"{icon} {s['user_request'][:50]}..."
        if st.button(label, key=s["id"]):
            selected_session_id = s["id"]

    st.divider()
    nb_bloque = sum(1 for s in sessions if s["status"] == "bloque")
    nb_alerte = sum(1 for s in sessions if s["status"] == "alerte")
    nb_ok = sum(1 for s in sessions if s["status"] == "ok")
    m1, m2, m3 = st.columns(3)
    m1.metric("OK", nb_ok)
    m2.metric("Alertes", nb_alerte)
    m3.metric("Bloquées", nb_bloque)

with col2:
    st.subheader("Détail de la session")
    if selected_session_id:
        try:
            detail = httpx.get(f"{AGENTGUARD_URL}/sessions/{selected_session_id}", timeout=10).json()
        except Exception as e:
            st.error(f"Erreur : {e}")
            detail = None

        if detail:
            session = detail["session"]
            st.markdown(f"**Demande client :** {session['user_request']}")
            st.markdown(f"**Statut final :** {status_icons.get(session['status'], '')} {session['status']}")

            st.markdown("### Trajectoire (étapes de l'agent)")
            for step in detail["steps"]:
                with st.expander(f"Étape {step['step_number']} — {step['tool_called'] or 'réponse finale'}"):
                    st.write("**Raisonnement :**", step["reasoning"])
                    if step["tool_called"]:
                        st.write("**Outil appelé :**", step["tool_called"])
                        st.write("**Paramètres :**", step["tool_params"])
                        st.write("**Résultat :**", step["tool_result"])

            if detail["alerts"]:
                st.markdown("### 🚨 Alertes (règles)")
                for a in detail["alerts"]:
                    st.warning(f"[{a['severity'].upper()}] {a['rule_triggered']} (étape {a['step_number']})")

            if detail["judgments"]:
                st.markdown("### 🧑‍⚖️ Verdict du juge IA")
                for j in detail["judgments"]:
                    st.info(
                        f"Anomalie détectée : {'Oui' if j['anomalie_detectee'] else 'Non'}\n\n"
                        f"Gravité : {j['gravite']}\n\n"
                        f"Raison : {j['raison']}\n\n"
                        f"Action recommandée : {j['action_recommandee']}"
                    )
    else:
        st.info("Sélectionne une session à gauche pour voir son détail.")

st.divider()
st.subheader("Tester une nouvelle demande")
with st.form("test_form"):
    message = st.text_area("Message client", placeholder="Je veux etre rembourse pour ma commande 1001...")
    submitted = st.form_submit_button("Envoyer via AgentGuard")
    if submitted and message:
        try:
            result = httpx.post(f"{AGENTGUARD_URL}/agent/query", json={"message": message}, timeout=60).json()
            st.success("Requête traitée, rafraîchis la page pour voir la session dans la liste.")
            st.json(result)
        except Exception as e:
            st.error(f"Erreur : {e}")