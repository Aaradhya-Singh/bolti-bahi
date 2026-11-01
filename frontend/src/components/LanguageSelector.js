"use client";

import { useState, useEffect } from "react";
import { Globe } from "lucide-react";

const LANGUAGES = [
  { code: "hi-IN", label: "हिंदी", labelEn: "Hindi" },
  { code: "mr-IN", label: "मराठी", labelEn: "Marathi" },
];

export default function LanguageSelector({ onChange }) {
  const [lang, setLang] = useState("hi-IN");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("bolti_bahi_lang");
    if (stored) {
      setLang(stored);
      onChange?.(stored);
    }
  }, []);

  function handleSelect(code) {
    setLang(code);
    localStorage.setItem("bolti_bahi_lang", code);
    onChange?.(code);
    setOpen(false);
  }

  const current = LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white border border-gray-200 text-sm font-medium text-gray-700 min-h-[44px] active:bg-gray-50 transition-colors"
        aria-label="भाषा चुनें (Select language)"
      >
        <Globe size={16} className="text-orange-500 shrink-0" />
        <span>{current.label}</span>
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-1 z-50 bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden min-w-[140px]">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => handleSelect(l.code)}
                className={`w-full text-left px-4 py-3 text-base font-medium transition-colors min-h-[44px] ${
                  lang === l.code
                    ? "bg-orange-50 text-orange-600"
                    : "text-gray-700 active:bg-gray-50"
                }`}
              >
                {l.label}
                <span className="text-xs text-gray-400 ml-2">
                  {l.labelEn}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
