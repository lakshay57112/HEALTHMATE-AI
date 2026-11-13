"""Curated, educational lab-parameter knowledge used for plain-language explanations.

These texts are general education (sourced from common patient-education material), never a
diagnosis. Phrasing is deliberately non-diagnostic: "can be associated with", "your doctor can
explain what this means for you". Reference ranges are NEVER taken from here — only from the
patient's own report.
"""
from __future__ import annotations

import re

# canonical -> aliases (lowercase, punctuation-insensitive)
ALIASES: dict[str, list[str]] = {
    "hemoglobin": ["haemoglobin", "hemoglobin", "hb", "hgb"],
    "hba1c": ["hba1c", "hbalc", "glycated haemoglobin", "glycated hemoglobin", "glycosylated hemoglobin", "a1c"],
    "fasting_glucose": ["fasting blood sugar", "fasting blood glucose", "fbs", "glucose fasting", "fasting plasma glucose", "blood sugar fasting"],
    "pp_glucose": ["post prandial blood sugar", "postprandial blood sugar", "ppbs", "glucose pp", "post prandial glucose", "blood sugar pp"],
    "random_glucose": ["random blood sugar", "rbs", "glucose random"],
    "total_cholesterol": ["total cholesterol", "cholesterol total", "serum cholesterol", "cholesterol"],
    "ldl": ["ldl cholesterol", "ldl", "ldl-c", "low density lipoprotein"],
    "hdl": ["hdl cholesterol", "hdl", "hdl-c", "high density lipoprotein"],
    "triglycerides": ["triglycerides", "triglyceride", "tg"],
    "vldl": ["vldl cholesterol", "vldl"],
    "non_hdl": ["non hdl cholesterol", "non-hdl cholesterol", "non hdl"],
    "creatinine": ["serum creatinine", "creatinine"],
    "urea": ["blood urea", "urea", "bun", "blood urea nitrogen"],
    "egfr": ["egfr", "estimated gfr"],
    "uric_acid": ["uric acid", "serum uric acid"],
    "tsh": ["tsh", "thyroid stimulating hormone"],
    "vitamin_d": ["vitamin d", "25-oh vitamin d", "25 hydroxy vitamin d", "vit d"],
    "vitamin_b12": ["vitamin b12", "vit b12", "cobalamin"],
    "sodium": ["sodium", "serum sodium", "na"],
    "potassium": ["potassium", "serum potassium", "k"],
    "alt": ["sgpt", "alt", "alanine aminotransferase"],
    "ast": ["sgot", "ast", "aspartate aminotransferase"],
    "platelets": ["platelet count", "platelets", "plt"],
    "wbc": ["total leucocyte count", "total wbc count", "wbc", "tlc", "white blood cells"],
    "rbc": ["rbc count", "rbc", "red blood cells"],
    "calcium": ["serum calcium", "calcium"],
}

_ALIAS_INDEX = sorted(((a, c) for c, al in ALIASES.items() for a in al), key=lambda x: -len(x[0]))


def canonicalize(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]+", " ", name.lower()).strip()
    n = re.sub(r"\s+", " ", n)
    # Ratios ("Cholesterol/HDL Ratio") and urine tests ("Urine Albumin/Creatinine") are different analytes from
    # the serum test whose name they contain — matching them would apply the wrong plausibility limits.
    if re.search(r"\b(ratio|index)\b", n) or re.match(r"(urine|urinary|spot urine|24 ?hr urine)\b", n):
        return re.sub(r"\s+", "_", n)[:60] or "unknown"
    for alias, canon in _ALIAS_INDEX:
        a = re.sub(r"[^a-z0-9 ]+", " ", alias)
        if n == a or n.startswith(a + " ") or f" {a} " in f" {n} " and len(a) > 3:
            return canon
    return re.sub(r"\s+", "_", n)[:60] or "unknown"


K = dict  # readability

KNOWLEDGE: dict[str, dict] = {
    "hemoglobin": K(label="Haemoglobin", label_hi="हीमोग्लोबिन",
        what="Haemoglobin carries oxygen in your blood.", what_hi="हीमोग्लोबिन खून में ऑक्सीजन ले जाता है।",
        low="A low value can be associated with anaemia, which may cause tiredness.", low_hi="कम होने पर खून की कमी (एनीमिया) हो सकती है, जिससे थकान लग सकती है।",
        high="A high value is less common and can be associated with dehydration or other causes.", high_hi="ज़्यादा होना कम आम है; यह पानी की कमी या अन्य कारणों से हो सकता है।",
        questions=["Is my haemoglobin level a concern?", "Should I change my diet or take supplements?"],
        questions_hi=["क्या मेरा हीमोग्लोबिन चिंता की बात है?", "क्या मुझे खाने में बदलाव या सप्लीमेंट लेने चाहिए?"]),
    "hba1c": K(label="HbA1c", label_hi="HbA1c (3 महीने की औसत शुगर)",
        what="HbA1c shows your average blood sugar over the last 2–3 months.", what_hi="HbA1c पिछले 2–3 महीनों की औसत ब्लड शुगर बताता है।",
        high="A higher value means average blood sugar has been above the lab's range.", high_hi="ज़्यादा होने का मतलब है कि औसत शुगर लैब की सीमा से ऊपर रही है।",
        low="A low value is uncommon; your doctor can explain it.", low_hi="कम होना आम नहीं है; डॉक्टर इसे समझा सकते हैं।",
        questions=["What HbA1c target is right for me?", "Do my medicines or diet need review?"],
        questions_hi=["मेरे लिए HbA1c का लक्ष्य क्या होना चाहिए?", "क्या मेरी दवाइयों या खाने की समीक्षा होनी चाहिए?"]),
    "fasting_glucose": K(label="Fasting blood sugar", label_hi="खाली पेट शुगर",
        what="Blood sugar measured after not eating for 8–10 hours.", what_hi="8–10 घंटे कुछ न खाने के बाद मापी गई शुगर।",
        high="Above the range means sugar was high even without food.", high_hi="सीमा से ज़्यादा होने का मतलब है कि बिना खाए भी शुगर ज़्यादा थी।",
        low="Below the range can cause shakiness or sweating; tell your doctor.", low_hi="कम होने पर कंपकंपी या पसीना आ सकता है; डॉक्टर को बताएं।",
        questions=["Is my fasting sugar in my target range?", "How often should I check it at home?"],
        questions_hi=["क्या मेरी खाली पेट शुगर लक्ष्य में है?", "घर पर कितनी बार जांच करूं?"]),
    "pp_glucose": K(label="Post-meal blood sugar", label_hi="खाने के बाद शुगर",
        what="Blood sugar about 2 hours after a meal.", what_hi="खाने के लगभग 2 घंटे बाद की शुगर।",
        high="Above the range means sugar rose more than expected after eating.", high_hi="सीमा से ज़्यादा होने का मतलब है कि खाने के बाद शुगर उम्मीद से ज़्यादा बढ़ी।",
        low="Below the range is uncommon after meals; mention it to your doctor.", low_hi="खाने के बाद कम होना आम नहीं; डॉक्टर को बताएं।",
        questions=["Should I change what I eat at meals?"], questions_hi=["क्या मुझे खाने में बदलाव करना चाहिए?"]),
    "random_glucose": K(label="Random blood sugar", label_hi="रैंडम शुगर", what="Blood sugar at any time of day.", what_hi="दिन में किसी भी समय की शुगर।",
        high="Above the range means sugar was high at the time of testing.", high_hi="जांच के समय शुगर ज़्यादा थी।", low="Below the range may cause weakness.", low_hi="कम होने पर कमज़ोरी लग सकती है।",
        questions=["Do I need a fasting or HbA1c test?"], questions_hi=["क्या मुझे खाली पेट या HbA1c जांच करवानी चाहिए?"]),
    "total_cholesterol": K(label="Total cholesterol", label_hi="कुल कोलेस्ट्रॉल", what="The total amount of cholesterol (a type of fat) in your blood.", what_hi="खून में कुल कोलेस्ट्रॉल (एक प्रकार की चर्बी)।",
        high="Higher levels can be associated with heart-health risk over time.", high_hi="ज़्यादा होने पर समय के साथ दिल की सेहत पर असर पड़ सकता है।", low="Low values are usually not a concern; ask your doctor.", low_hi="कम होना आमतौर पर चिंता नहीं; डॉक्टर से पूछें।",
        questions=["Is my cholesterol a risk for my heart?", "Which foods should I reduce?"], questions_hi=["क्या मेरा कोलेस्ट्रॉल दिल के लिए जोखिम है?", "कौन से खाने कम करूं?"]),
    "ldl": K(label="LDL ('bad') cholesterol", label_hi="LDL (खराब) कोलेस्ट्रॉल", what="LDL can build up in blood vessels.", what_hi="LDL खून की नलियों में जम सकता है।",
        high="Higher LDL can be associated with heart and blood-vessel risk.", high_hi="ज़्यादा LDL दिल और नसों के जोखिम से जुड़ा हो सकता है।", low="Low LDL is usually fine.", low_hi="कम LDL आमतौर पर ठीक है।",
        questions=["What LDL target should I aim for?"], questions_hi=["मेरा LDL लक्ष्य क्या होना चाहिए?"]),
    "hdl": K(label="HDL ('good') cholesterol", label_hi="HDL (अच्छा) कोलेस्ट्रॉल", what="HDL helps remove extra cholesterol.", what_hi="HDL अतिरिक्त कोलेस्ट्रॉल हटाने में मदद करता है।",
        low="Lower HDL can be associated with higher heart risk.", low_hi="कम HDL दिल के ज़्यादा जोखिम से जुड़ा हो सकता है।", high="Higher HDL is usually considered good.", high_hi="ज़्यादा HDL आमतौर पर अच्छा माना जाता है।",
        questions=["How can I improve my HDL?"], questions_hi=["मैं अपना HDL कैसे बढ़ा सकता/सकती हूं?"]),
    "triglycerides": K(label="Triglycerides", label_hi="ट्राइग्लिसराइड्स", what="A type of fat in the blood, affected by food and sugar.", what_hi="खून में एक प्रकार की चर्बी, जो खाने और शुगर से प्रभावित होती है।",
        high="Higher levels can be associated with diet, sugar control and heart risk.", high_hi="ज़्यादा होना खान-पान, शुगर और दिल के जोखिम से जुड़ा हो सकता है।", low="Low levels are usually not a concern.", low_hi="कम होना आमतौर पर चिंता नहीं।",
        questions=["Could my diet be raising triglycerides?"], questions_hi=["क्या मेरा खाना ट्राइग्लिसराइड्स बढ़ा रहा है?"]),
    "creatinine": K(label="Creatinine", label_hi="क्रिएटिनिन", what="A waste product that shows how well kidneys filter blood.", what_hi="एक अपशिष्ट पदार्थ जो बताता है कि किडनी कितना अच्छा काम कर रही है।",
        high="A higher value can be associated with reduced kidney filtering. Diet changes (like high protein) should be discussed with your doctor.", high_hi="ज़्यादा होना किडनी के कम काम करने से जुड़ा हो सकता है। प्रोटीन जैसे खाने के बदलाव डॉक्टर से पूछकर करें।",
        low="A low value is usually not a concern.", low_hi="कम होना आमतौर पर चिंता नहीं।",
        questions=["Is my kidney function okay?", "Are there foods or medicines I should avoid?"], questions_hi=["क्या मेरी किडनी ठीक काम कर रही है?", "क्या कोई खाना या दवा मुझे नहीं लेनी चाहिए?"]),
    "urea": K(label="Blood urea", label_hi="ब्लड यूरिया", what="Another waste product filtered by the kidneys.", what_hi="एक और अपशिष्ट जिसे किडनी साफ़ करती है।",
        high="Higher values can be associated with dehydration, high protein intake or kidney function.", high_hi="ज़्यादा होना पानी की कमी, ज़्यादा प्रोटीन या किडनी से जुड़ा हो सकता है।", low="Low values are usually not a concern.", low_hi="कम होना आमतौर पर चिंता नहीं।",
        questions=["Should I drink more water?"], questions_hi=["क्या मुझे ज़्यादा पानी पीना चाहिए?"]),
    "egfr": K(label="eGFR", label_hi="eGFR (किडनी फ़िल्टर दर)", what="An estimate of how well your kidneys filter.", what_hi="किडनी कितनी अच्छी तरह खून साफ़ करती है, इसका अनुमान।",
        low="A lower eGFR can be associated with reduced kidney function.", low_hi="कम eGFR किडनी के कम काम करने से जुड़ा हो सकता है।", high="A higher eGFR is usually fine.", high_hi="ज़्यादा eGFR आमतौर पर ठीक है।",
        questions=["What stage is my kidney function in?"], questions_hi=["मेरी किडनी किस स्थिति में है?"]),
    "uric_acid": K(label="Uric acid", label_hi="यूरिक एसिड", what="A waste product from breaking down certain foods.", what_hi="कुछ खाने टूटने से बनने वाला अपशिष्ट।",
        high="Higher levels can be associated with joint pain (gout) or kidney stones.", high_hi="ज़्यादा होना जोड़ों के दर्द (गठिया) या पथरी से जुड़ा हो सकता है।", low="Low levels are uncommon.", low_hi="कम होना आम नहीं।",
        questions=["Do I need to change my diet for uric acid?"], questions_hi=["क्या यूरिक एसिड के लिए खाना बदलूं?"]),
    "tsh": K(label="TSH (thyroid)", label_hi="TSH (थायरॉइड)", what="TSH controls your thyroid gland.", what_hi="TSH थायरॉइड ग्रंथि को नियंत्रित करता है।",
        high="A high TSH can be associated with an underactive thyroid.", high_hi="ज़्यादा TSH थायरॉइड के कम काम करने से जुड़ा हो सकता है।", low="A low TSH can be associated with an overactive thyroid.", low_hi="कम TSH थायरॉइड के ज़्यादा काम करने से जुड़ा हो सकता है।",
        questions=["Does my thyroid medicine dose need review?"], questions_hi=["क्या मेरी थायरॉइड दवा की समीक्षा होनी चाहिए?"]),
    "vitamin_d": K(label="Vitamin D", label_hi="विटामिन D", what="Vitamin D supports bones and muscles.", what_hi="विटामिन D हड्डियों और मांसपेशियों के लिए ज़रूरी है।",
        low="Low vitamin D is common and can affect bone strength.", low_hi="विटामिन D की कमी आम है और हड्डियों को कमज़ोर कर सकती है।", high="Very high levels usually come from supplements.", high_hi="बहुत ज़्यादा स्तर आमतौर पर सप्लीमेंट से होता है।",
        questions=["Do I need vitamin D supplements?"], questions_hi=["क्या मुझे विटामिन D सप्लीमेंट चाहिए?"]),
    "vitamin_b12": K(label="Vitamin B12", label_hi="विटामिन B12", what="B12 supports nerves and blood formation.", what_hi="B12 नसों और खून बनने के लिए ज़रूरी है।",
        low="Low B12 can cause tiredness or tingling; common in vegetarians and with some diabetes medicines.", low_hi="B12 की कमी से थकान या झनझनाहट हो सकती है; शाकाहारियों में आम है।", high="High levels are usually from supplements.", high_hi="ज़्यादा स्तर आमतौर पर सप्लीमेंट से होता है।",
        questions=["Should I take B12 supplements?"], questions_hi=["क्या मुझे B12 सप्लीमेंट लेने चाहिए?"]),
    "sodium": K(label="Sodium", label_hi="सोडियम", what="A salt that balances water in your body.", what_hi="एक नमक जो शरीर में पानी का संतुलन रखता है।",
        low="Low sodium can cause confusion or weakness, especially in elderly people.", low_hi="कम सोडियम से भ्रम या कमज़ोरी हो सकती है, खासकर बुज़ुर्गों में।", high="High sodium can be associated with dehydration.", high_hi="ज़्यादा सोडियम पानी की कमी से जुड़ा हो सकता है।",
        questions=["Is my salt level safe?"], questions_hi=["क्या मेरा नमक का स्तर सुरक्षित है?"]),
    "potassium": K(label="Potassium", label_hi="पोटैशियम", what="A mineral important for heart rhythm and muscles.", what_hi="दिल की धड़कन और मांसपेशियों के लिए ज़रूरी खनिज।",
        high="High potassium needs attention — some foods (like bananas) may need limiting only if your doctor says so.", high_hi="ज़्यादा पोटैशियम पर ध्यान ज़रूरी है — केला जैसे खाने केवल डॉक्टर के कहने पर कम करें।",
        low="Low potassium can cause cramps or weakness.", low_hi="कम पोटैशियम से ऐंठन या कमज़ोरी हो सकती है।", questions=["Do I need to change potassium in my diet?"], questions_hi=["क्या मुझे खाने में पोटैशियम बदलना चाहिए?"]),
    "alt": K(label="SGPT / ALT (liver)", label_hi="SGPT / ALT (लिवर)", what="A liver enzyme.", what_hi="लिवर का एक एंज़ाइम।", high="Higher values can be associated with liver stress from many causes.", high_hi="ज़्यादा होना कई कारणों से लिवर पर दबाव से जुड़ा हो सकता है।",
        low="Low values are not usually a concern.", low_hi="कम होना आमतौर पर चिंता नहीं।", questions=["Is my liver function okay?"], questions_hi=["क्या मेरा लिवर ठीक है?"]),
    "ast": K(label="SGOT / AST (liver)", label_hi="SGOT / AST (लिवर)", what="An enzyme found in the liver and muscles.", what_hi="लिवर और मांसपेशियों में मिलने वाला एंज़ाइम।", high="Higher values can be associated with liver or muscle stress.", high_hi="ज़्यादा होना लिवर या मांसपेशियों पर दबाव से जुड़ा हो सकता है।",
        low="Low values are not usually a concern.", low_hi="कम होना आमतौर पर चिंता नहीं।", questions=["Do I need a repeat liver test?"], questions_hi=["क्या लिवर जांच दोबारा करवानी चाहिए?"]),
    "platelets": K(label="Platelets", label_hi="प्लेटलेट्स", what="Platelets help blood clot.", what_hi="प्लेटलेट्स खून का थक्का बनाने में मदद करते हैं।", low="Low platelets can increase bleeding or bruising.", low_hi="कम प्लेटलेट्स से खून ज़्यादा बह सकता है या नील पड़ सकते हैं।",
        high="High platelets can have many causes.", high_hi="ज़्यादा प्लेटलेट्स के कई कारण हो सकते हैं।", questions=["Is my platelet count a concern?"], questions_hi=["क्या प्लेटलेट्स चिंता की बात है?"]),
    "wbc": K(label="White blood cells", label_hi="सफेद रक्त कोशिकाएं", what="WBCs fight infection.", what_hi="सफेद रक्त कोशिकाएं संक्रमण से लड़ती हैं।", high="High values are often seen with infection or inflammation.", high_hi="ज़्यादा होना अक्सर संक्रमण या सूजन में दिखता है।",
        low="Low values can reduce infection-fighting ability.", low_hi="कम होने से संक्रमण से लड़ने की क्षमता घट सकती है।", questions=["Do I have an infection?"], questions_hi=["क्या मुझे कोई संक्रमण है?"]),
    "rbc": K(label="Red blood cells", label_hi="लाल रक्त कोशिकाएं", what="RBCs carry oxygen.", what_hi="लाल रक्त कोशिकाएं ऑक्सीजन ले जाती हैं।", low="Low values can be associated with anaemia.", low_hi="कम होना एनीमिया से जुड़ा हो सकता है।",
        high="High values can have several causes.", high_hi="ज़्यादा होने के कई कारण हो सकते हैं।", questions=["Is my blood count normal for me?"], questions_hi=["क्या मेरा ब्लड काउंट मेरे लिए सामान्य है?"]),
    "calcium": K(label="Calcium", label_hi="कैल्शियम", what="Calcium keeps bones and nerves healthy.", what_hi="कैल्शियम हड्डियों और नसों को स्वस्थ रखता है।", low="Low calcium can cause cramps.", low_hi="कम कैल्शियम से ऐंठन हो सकती है।",
        high="High calcium needs your doctor's review.", high_hi="ज़्यादा कैल्शियम की डॉक्टर से समीक्षा ज़रूरी है।", questions=["Do I need calcium supplements?"], questions_hi=["क्या मुझे कैल्शियम सप्लीमेंट चाहिए?"]),
}

# Physiologically implausible values usually indicate an OCR/reading error (not a range for diagnosis).
PLAUSIBLE_LIMITS: dict[str, tuple[float, float]] = {
    "hemoglobin": (2, 25), "hba1c": (2, 20), "fasting_glucose": (15, 1000), "pp_glucose": (15, 1200), "random_glucose": (15, 1200),
    "total_cholesterol": (40, 800), "ldl": (5, 600), "hdl": (5, 200), "triglycerides": (10, 5000), "creatinine": (0.1, 25),
    "urea": (1, 400), "tsh": (0.001, 150), "vitamin_d": (1, 250), "vitamin_b12": (20, 5000), "sodium": (100, 180), "potassium": (1.5, 9),
    "platelets": (1, 2000), "uric_acid": (0.5, 20), "calcium": (4, 16),
}

# Brand -> generic (only used when a brand is clearly written; marked as dictionary-sourced).
BRAND_TO_GENERIC: dict[str, str] = {
    "glycomet": "Metformin", "gluconorm": "Metformin", "obimet": "Metformin", "telma": "Telmisartan", "ecosprin": "Aspirin",
    "thyronorm": "Levothyroxine", "eltroxin": "Levothyroxine", "atorva": "Atorvastatin", "lipitor": "Atorvastatin", "rosuvas": "Rosuvastatin",
    "amlong": "Amlodipine", "amlopress": "Amlodipine", "pan": "Pantoprazole", "pan 40": "Pantoprazole", "pantocid": "Pantoprazole",
    "dolo": "Paracetamol", "crocin": "Paracetamol", "calpol": "Paracetamol", "shelcal": "Calcium + Vitamin D3", "janumet": "Sitagliptin + Metformin",
    "galvus": "Vildagliptin", "amaryl": "Glimepiride", "glimy": "Glimepiride", "losar": "Losartan", "repace": "Losartan", "neurobion": "Vitamin B complex",
    "clopilet": "Clopidogrel", "metolar": "Metoprolol", "concor": "Bisoprolol", "uprise d3": "Cholecalciferol", "zyloric": "Allopurinol",
}

# Common single-unit strengths (mg) for a sanity check — flags unusual values for pharmacist confirmation.
STRENGTH_RANGES_MG: dict[str, tuple[float, float]] = {
    "metformin": (250, 1000), "telmisartan": (20, 80), "aspirin": (75, 650), "atorvastatin": (5, 80), "rosuvastatin": (5, 40),
    "amlodipine": (2.5, 10), "pantoprazole": (20, 40), "paracetamol": (125, 1000), "glimepiride": (0.5, 4), "losartan": (25, 100),
    "levothyroxine": (0.0125, 0.3), "clopidogrel": (75, 300), "metoprolol": (12.5, 200), "allopurinol": (100, 300),
}

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)",
    r"disregard (the )?(system|previous|above)",
    r"you are now", r"system prompt", r"developer mode", r"act as (an? )?(admin|doctor|system)",
    r"(send|email|forward|post) (this|the|all|my) .{0,40}(to|at) ", r"https?://", r"\bprescribe\b.{0,30}\bincrease\b",
    r"new instructions?:", r"override (the )?(safety|rules|instructions)", r"<\s*/?\s*(system|instructions?)\s*>",
    r"\btell the (patient|user)\b", r"\bdo not (mention|reveal|disclose) (this|these|the instructions)",
    r"\bmark (every|all) .{0,25}\bnormal\b", r"\b(ai|assistant|chatbot|language model)\b.{0,20}\b(must|should) (now )?(ignore|obey|follow)",
]


def strip_injection_lines(text: str) -> str:
    """Drop lines that look like instructions to an AI, so they can never become extracted data."""
    return "\n".join(ln for ln in (text or "").splitlines() if not scan_injection(ln))


def scan_injection(text: str) -> list[str]:
    hits = []
    low = (text or "").lower()
    for p in INJECTION_PATTERNS:
        m = re.search(p, low)
        if m:
            hits.append(m.group(0)[:60])
    return hits
