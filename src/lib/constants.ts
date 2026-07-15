export const CATEGORY_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  work:        { bg: "hsl(217 91% 95%)", text: "hsl(217 91% 40%)", bar: "hsl(217 91% 60%)" },
  finance:     { bg: "hsl(142 71% 93%)", text: "hsl(142 71% 30%)", bar: "hsl(142 71% 45%)" },
  personal:    { bg: "hsl(280 65% 94%)", text: "hsl(280 65% 40%)", bar: "hsl(280 65% 60%)" },
  travel:      { bg: "hsl(33 100% 93%)", text: "hsl(33 100% 35%)", bar: "hsl(33 100% 50%)" },
  receipts:    { bg: "hsl(190 90% 93%)", text: "hsl(190 90% 30%)", bar: "hsl(190 90% 45%)" },
  social:      { bg: "hsl(340 75% 94%)", text: "hsl(340 75% 40%)", bar: "hsl(340 75% 55%)" },
  newsletters: { bg: "hsl(45 93% 93%)",  text: "hsl(45 93% 30%)",  bar: "hsl(45 93% 47%)"  },
  promotions:  { bg: "hsl(265 80% 94%)", text: "hsl(265 80% 40%)", bar: "hsl(265 80% 60%)" },
};

export const CATEGORY_LABELS: Record<string, string> = {
  work: "Work",
  finance: "Finance",
  personal: "Personal",
  travel: "Travel",
  receipts: "Receipts",
  social: "Social",
  newsletters: "Newsletters",
  promotions: "Promotions",
};

export const CATEGORY_ICONS: Record<string, string> = {
  work: "💼",
  finance: "💰",
  personal: "👤",
  travel: "✈️",
  receipts: "🧾",
  social: "🌐",
  newsletters: "📰",
  promotions: "🏷️",
};
