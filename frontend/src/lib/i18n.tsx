"use client";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "en" | "hi";

const HI: Record<string, string> = {
  // navigation
  Overview: "सारांश", "Medical Reports": "मेडिकल रिपोर्ट", Medicines: "दवाइयां", Nutrition: "पोषण", Appointments: "अपॉइंटमेंट", "Health History": "स्वास्थ्य इतिहास",
  "Family & Caretakers": "परिवार और देखभालकर्ता", "AI Health Assistant": "AI स्वास्थ्य सहायक", Settings: "सेटिंग्स", Home: "होम", Assistant: "सहायक", More: "और", Reports: "रिपोर्ट",
  Notifications: "सूचनाएं", Profile: "प्रोफ़ाइल", "Sign out": "साइन आउट", Documents: "दस्तावेज़", Family: "परिवार", History: "इतिहास",
  // greetings
  "Good morning": "सुप्रभात", "Good afternoon": "नमस्कार", "Good evening": "शुभ संध्या",
  "Here's your health today": "आज आपका स्वास्थ्य", "Upload a document": "दस्तावेज़ अपलोड करें",
  // dashboard
  "Next medicine": "अगली दवा", "Today's medicines": "आज की दवाइयां", "Medicine adherence": "दवा नियमितता", "Last 7 days": "पिछले 7 दिन", "Today's meals": "आज का भोजन",
  "Upcoming appointment": "आने वाला अपॉइंटमेंट", "Recent reports": "हाल की रिपोर्ट", "Health measurements": "स्वास्थ्य माप", "Family connection": "परिवार से जुड़ाव",
  "Blood pressure": "ब्लड प्रेशर", "Blood glucose": "ब्लड शुगर", "Heart rate": "धड़कन", Weight: "वज़न", "View all": "सभी देखें", "See schedule": "समय-सारणी देखें",
  "All done for today": "आज की सभी दवाइयां हो गईं", "No medicines yet": "अभी कोई दवा नहीं", "Needs your review": "आपकी पुष्टि ज़रूरी", "Sample data": "नमूना डेटा",
  "Taken": "ली गई", "Skipped": "छोड़ी", "Missed": "छूट गई", "Due now": "अभी लें", "Upcoming": "आने वाली", "Not confirmed": "पुष्टि बाकी", "Snoozed": "बाद में",
  "Mark taken": "ले ली", "Skip": "छोड़ें", "Remind later": "बाद में याद दिलाएं", Morning: "सुबह", Afternoon: "दोपहर", Evening: "शाम", Night: "रात",
  Breakfast: "नाश्ता", Lunch: "दोपहर का भोजन", Snack: "शाम का नाश्ता", Dinner: "रात का भोजन", "Before food": "खाने से पहले", "After food": "खाने के बाद",
  "Connected": "जुड़े हुए", "Invite pending": "निमंत्रण बाकी", "Not connected": "कोई नहीं जुड़ा", "Add family member": "परिवार का सदस्य जोड़ें",
  // actions
  Save: "सहेजें", Cancel: "रद्द करें", Confirm: "पुष्टि करें", Continue: "आगे बढ़ें", Back: "वापस", Edit: "बदलें", Delete: "हटाएं", Add: "जोड़ें", Done: "हो गया",
  "Add medicine": "दवा जोड़ें", "Upload prescription": "पर्चा अपलोड करें", "Upload report": "रिपोर्ट अपलोड करें", "Try a sample": "नमूना आज़माएं", "Ask a question": "प्रश्न पूछें",
  "Confirm and save": "पुष्टि करें और सहेजें", Search: "खोजें", Filter: "फ़िल्टर", Retry: "फिर से कोशिश करें", "Ate": "खा लिया", Delayed: "देर होगी",
  // reports
  "Simple explanation": "आसान भाषा में", "Questions to ask your doctor": "डॉक्टर से पूछने के प्रश्न", Normal: "सामान्य", High: "ज़्यादा", Low: "कम", "No range": "सीमा नहीं",
  "Important findings": "मुख्य बातें", "Compared with last report": "पिछली रिपोर्ट से तुलना", "All results": "सभी परिणाम",
  // misc
  Language: "भाषा", "Large text": "बड़े अक्षर", "Voice reminders": "आवाज़ में याद दिलाना", Privacy: "गोपनीयता", "Not medical advice": "चिकित्सा सलाह नहीं",
  "Type your question…": "अपना प्रश्न लिखें…", Send: "भेजें", "Speak": "बोलें", Listening: "सुन रहा हूं", "Weekly meal planner": "साप्ताहिक भोजन योजना",
  "Meal schedule": "भोजन का समय", Recipes: "रेसिपी", Ingredients: "सामग्री", Preparation: "बनाने की विधि", Substitutions: "विकल्प", "Why this suits you": "यह आपके लिए क्यों सही है",
  Calories: "कैलोरी", Protein: "प्रोटीन", Carbs: "कार्ब्स", Fat: "वसा", Fibre: "फ़ाइबर", Sodium: "सोडियम",
};

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (s: string) => string };
const I18nContext = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (s) => s });

export function I18nProvider({ children, initial = "en" }: { children: React.ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("hm_lang") as Lang | null;
      if (saved === "en" || saved === "hi") setLangState(saved);
    } catch {}
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const value = useMemo<Ctx>(
    () => ({
      lang,
      setLang: (l) => {
        setLangState(l);
        try {
          localStorage.setItem("hm_lang", l);
        } catch {}
      },
      t: (s) => (lang === "hi" ? HI[s] ?? s : s),
    }),
    [lang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);
