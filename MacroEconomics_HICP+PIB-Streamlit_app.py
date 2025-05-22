import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- Función para detectar país desde dirección ---
def obtener_codigo_pais(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": direccion, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "macro-app/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers)
        data = r.json()
        if data:
            return data[0]["address"].get("country_code", "").upper()
    except Exception as e:
        st.error(f"Error detectando país: {e}")
    return None

# --- UI ---
st.title("📊 Macroeconomic Summary Generator (HICP + GDP)")
direccion = st.text_input("Enter a European address:")
longitud = st.slider("Number of words in the summary:", 100, 300, 150, step=25)
kpis_seleccionados = st.multiselect(
    "Select the indicators to include in the summary:",
    ["HICP – Harmonized Inflation", "GDP – Gross Domestic Product"]
)

# --- Carga si hay dirección y KPIs ---
if st.button("Generate Summary") and direccion and kpis_seleccionados:
    codigo_pais = obtener_codigo_pais(direccion)
    if not codigo_pais:
        st.error("❌ Could not detect the country from the address.")
    else:
        nombre_pais = {
            "NL": "Países Bajos", "ES": "España", "FR": "Francia",
            "IT": "Italia", "DE": "Alemania", "BE": "Bélgica",
            "PT": "Portugal", "AT": "Austria"
        }.get(codigo_pais, f"País ({codigo_pais})")

        anio_corte = datetime.today().year - 5

        def obtener_df(dataset, extra_params):
            url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
            params = {"format": "JSON", "lang": "EN", "geo": codigo_pais}
            params.update(extra_params)
            r = requests.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            idx = data["dimension"]["time"]["category"]["index"]
            lbl = data["dimension"]["time"]["category"]["label"]
            ix_map = {str(v): lbl[k] for k, v in idx.items()}
            valores = [{"Periodo": ix_map[k], "Valor": v} for k, v in data["value"].items()]
            df = pd.DataFrame(valores)
            df = df[df["Periodo"].str[:4].astype(int) >= anio_corte]
            df["Periodo"] = pd.PeriodIndex(df["Periodo"], freq='Q').astype(str)
            return df

        texto_kpis = ""
        prompts = []

        try:
            if "HICP – Harmonized Inflation" in kpis_seleccionados:
                df_hicp = obtener_df("prc_hicp_midx", {"coicop": "CP00", "unit": "I15"})
                st.subheader("📈 HICP – Harmonized Inflation Index")
                fig1, ax1 = plt.subplots(figsize=(10, 3))
                ax1.plot(df_hicp["Periodo"], df_hicp["Valor"], color="#DAA520", linewidth=2)
                ax1.set_facecolor("#F5F5F5")
                ax1.tick_params(axis="x", rotation=45)
                ax1.set_ylabel("HICP Index")
                ax1.grid(True, linestyle="--", alpha=0.4)
                st.pyplot(fig1)
                texto_kpis += f"\n\n📌 HICP – Harmonized Inflation Index:\n{df_hicp.to_string(index=False)}"

            if "GDP – Gross Domestic Product" in kpis_seleccionados:
                df_pib = obtener_df("namq_10_gdp", {
                    "na_item": "B1GQ",
                    "unit": "CLV10_MNAC",
                    "s_adj": "NSA"
                })
                st.subheader("📉 GDP – Quarterly Volume (chain-linked)")
                fig2, ax2 = plt.subplots(figsize=(10, 3))
                ax2.plot(df_pib["Periodo"], df_pib["Valor"], color="#4682B4", linewidth=2)
                ax2.set_facecolor("#F5F5F5")
                ax2.tick_params(axis="x", rotation=45)
                ax2.set_ylabel("GDP (national unit)")
                ax2.grid(True, linestyle="--", alpha=0.4)
                st.pyplot(fig2)
                texto_kpis += f"\n\n📌 GDP – Quarterly Volume:\n{df_pib.to_string(index=False)}"

            prompt_es = f"""
Eres un economista. Redacta un resumen macroeconómico técnico de aproximadamente {longitud} palabras sobre los siguientes indicadores reales de {nombre_pais} extraídos de Eurostat:

{texto_kpis}

Escribe un párrafo independiente por cada indicador (por ejemplo, uno para la inflación, otro para el PIB, etc.), analizando su evolución y contexto. Finaliza con un párrafo que los relacione y cierre la conclusión. El texto debe estar en español.
"""

            prompt_en = f"""
You are an economist. Write a technical macroeconomic summary of approximately {longitud} words about the following real indicators for {nombre_pais}, extracted from Eurostat:

{texto_kpis}

Write one separate paragraph for each indicator (e.g., one for inflation, one for GDP, etc.), analyzing its trend and context. End with a final paragraph that connects them and concludes. The text must be in English.
"""

            # GPT
            respuesta_es = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_es}],
                temperature=0.6
            )
            respuesta_en = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_en}],
                temperature=0.6
            )

            st.subheader("🧠 Resumen en español")
            st.write(respuesta_es.choices[0].message.content.strip())

            st.subheader("🧠 Summary in English")
            st.write(respuesta_en.choices[0].message.content.strip())

        except Exception as e:
            st.error(f"❌ Error al procesar: {e}")

