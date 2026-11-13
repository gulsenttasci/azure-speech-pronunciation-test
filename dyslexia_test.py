import gradio as gr
import json
import azure.cognitiveservices.speech as speechsdk
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

load_dotenv()

speech_key = os.getenv("AZURE_SPEECH_KEY")
service_region = os.getenv("AZURE_SPEECH_REGION")

speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
LANGUAGE = "tr-TR"

DYSLEXIA_RULES = {
    "dolap": {
        "d": {
            "hata_tipi": "b/d Ayna Terslemesi",
            "tavsiye": "İlk sesi söylerken dudaklarını birleştirmek yerine, dilinin ucunu üst dişlerine değdirerek 'd' demeyi dene.",
        },
        "p": {
            "hata_tipi": "p/b Ötümlülük Karışıklığı",
            "tavsiye": "Sondaki 'p' sesini çok yumuşak söyledin. Ağzından küçük bir nefes patlaması çıkararak 'p' de.",
        },
    },
    "balık": {
        "b": {
            "hata_tipi": "b/d Ayna Terslemesi",
            "tavsiye": "İlk harfi söylerken dilini değil, iki dudağını birleştirerek 'b' demelisin.",
        },
        "k": {
            "hata_tipi": "k/g veya yutma",
            "tavsiye": "Kelimenin sonundaki 'k' sesini yuttun veya 'g' gibi söyledin. Boğazının arkasından net bir 'k' çıkar.",
        },
    },
    "tarak": {
        "t": {
            "hata_tipi": "t/d Sert-Yumuşak Kayması",
            "tavsiye": "Baştaki 't' sesini 'd' gibi söyledin. Biraz daha sert ve keskin bir 't' ile başla.",
        },
        "r": {
            "hata_tipi": "Fonem Yutma / Atlama",
            "tavsiye": "Ortadaki 'r' sesini unuttun. Dilini titreterek 'r' sesini vurgula.",
        },
    },
}


def analyze_speech(audio_path, target_word):
    if not audio_path:
        return "Lütfen ses kaydedin.", "", ""

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    speech_config.speech_recognition_language = LANGUAGE
    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=target_word,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pronunciation_config.phoneme_alphabet = "IPA"

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )
    pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        raw_json = result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        data = json.loads(raw_json)
        words = data.get("NBest", [{}])[0].get("Words", [])

        if not words:
            return "Kelime anlaşılamadı.", "", ""

        word_data = words[0]
        genel_skor = word_data.get("PronunciationAssessment", {}).get(
            "AccuracyScore", 0.0
        )

        # UI Hazırlığı
        score_md = f"### 🎯 Genel Telaffuz Skoru: **%{genel_skor:.1f}**\n\n"
        table_md = "| Harf | Skor | Durum |\n|:---:|:---:|:---:|\n"
        diagnostics_md = "### 🧠 Kural Motoru Teşhisi ve Geri Bildirim\n\n"

        hata_bulundu = False
        rules = DYSLEXIA_RULES.get(target_word, {})

        """
        # Fonem Analizi ve Kural İşletimi
        for p in word_data.get("Phonemes", []):
            # char = p.get("Phoneme", "?").lower()
            char = p.get("Phoneme") or p.get("Words") or "?"
            score = p.get("PronunciationAssessment", {}).get("AccuracyScore", 0.0)

            if score >= 60.0:
                table_md += f"| **/{char}/** | %{score:.1f} | 🟢 Başarılı |\n"
            else:
                table_md += f"| **/{char}/** | %{score:.1f} | 🔴 Hata |\n"

                # Kural motorunda bu harf için özel bir disleksi tuzağı tanımlı mı?
                if char in rules:
                    hata_bulundu = True
                    diagnostics_md += (
                        f"- **Tespit Edilen Karışıklık:** {rules[char]['hata_tipi']}\n"
                    )
                    diagnostics_md += f"  - 🧑‍🏫 **Öğretmen Robot Diyor ki:** *\"{rules[char]['tavsiye']}\"*\n\n"
                    """
        # Fonem Analizi
        for idx, p in enumerate(word_data.get("Phonemes", [])):
            # 1. Azure'dan harfi almaya çalış, alamazsan kelimedeki sırasına göre (idx) kendin bul
            char_from_azure = p.get("Phoneme") or p.get("Name") or ""
            if char_from_azure:
                char = char_from_azure.lower()
            else:
                char = target_word[idx].lower() if idx < len(target_word) else "?"

            score = p.get("PronunciationAssessment", {}).get("AccuracyScore", 0.0)

            if score >= 60.0:
                table_md += f"| **/{char}/** | %{score:.1f} | 🟢 Başarılı |\n"
            else:
                table_md += f"| **/{char}/** | %{score:.1f} | 🔴 Hata |\n"

                # Kural motorunda bu harf için disleksi tuzağı tanımlı mı?
                if char in rules:
                    hata_bulundu = True
                    diagnostics_md += (
                        f"- **Tespit Edilen Karışıklık:** {rules[char]['hata_tipi']}\n"
                    )
                    diagnostics_md += f"  - 🧑‍🏫 **Öğretmen Diyor ki:** *\"{rules[char]['tavsiye']}\"*\n\n"

        if not hata_bulundu:
            diagnostics_md += "✅ Harika okudun! Herhangi bir harf karışıklığı veya atlama tespit edilmedi."

        return score_md, table_md, diagnostics_md

    return "Ses işlenemedi.", "", ""


#GRADIO test için
with gr.Blocks() as demo:
    gr.Markdown("# 🧩 Yapay Zeka Destekli Disleksi Ses Analiz Prototipi")
    gr.Markdown(
        "Çocuğun yaptığı hataları disleksi örüntülerine göre yakalayıp pedagojik geri bildirim üretir."
    )

    with gr.Row():
        with gr.Column(scale=1):
            word_choice = gr.Radio(
                choices=list(DYSLEXIA_RULES.keys()),
                value="dolap",
                label="Test Kelimesini Seçin",
            )
            audio_in = gr.Audio(
                sources=["microphone"], type="filepath", label="Mikrofona Konuş"
            )
            btn = gr.Button("Analiz Et", variant="primary")

        with gr.Column(scale=2):
            out_score = gr.Markdown()
            out_diag = gr.Markdown()
            out_table = gr.Markdown()

    btn.click(
        fn=analyze_speech,
        inputs=[audio_in, word_choice],
        outputs=[out_score, out_table, out_diag],
    )

if __name__ == "__main__":
    # port 7860
    demo.launch(server_name="127.0.0.1", server_port=7860, ssr_mode=False)
