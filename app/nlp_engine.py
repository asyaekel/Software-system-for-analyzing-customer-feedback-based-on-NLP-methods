import os
import re
import numpy as np
from setfit import SetFitModel

class PureNLPFeedbackAnalyzer:
    def __init__(self):
        print("Ініціалізація донавченої NLP-моделі (SetFit)...")
        model_path = "setfit_absa_model"
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Не знайдено навчену модель у папці '{model_path}'. "
                "Будь ласка, спочатку запустіть 'python train_setfit.py' для її генерації."
            )
            
        # Завантажуємо нашу власну легку та розумну модель
        self.model = SetFitModel.from_pretrained(model_path)
        
        # Наші розширені критерії
        self.aspects = [
            "якість товару",
            "швидкість доставки",
            "робота служби підтримки",
            "ціна",
            "зручність використання сайту",
            "пакування",
            "асортимент та наявність",
            "процес повернення та гарантія",
            "програма лояльності та знижки",
            "бажання рекомендувати",
            "загальне задоволення від покупки"
        ]

        # Словник ключових слів (коренів слів) для безпомилкового пошуку тем
        self.keywords = {
            "якість товару": ["якість", "товар", "матеріал", "збірка", "працює", "річ", "пластик", "зроблено", "служить", "крісл", "куртк"],
            "швидкість доставки": ["доставк", "кур'єр", "привез", "чека", "посилк", "логістик", "запізн", "відправи"],
            "робота служби підтримки": ["підтримк", "менеджер", "оператор", "консультант", "відпові", "чат", "кол-центр", "допомог"],
            "ціна": ["цін", "грош", "дорого", "дешев", "вартіст", "прайс", "переплати", "вигідн"],
            "зручність використання сайту": ["сайт", "додаток", "інтерфейс", "кошик", "фільтр", "оформ", "клік", "баг", "висне"],
            "пакування": ["пакуван", "коробк", "упаковк", "плівк", "картон", "запакув", "розпакув"],
            "асортимент та наявність": ["асортимент", "наявніст", "вибір", "каталог", "розмір", "колір", "знайшов", "склад"],
            "процес повернення та гарантія": ["гаранті", "повернен", "поверну", "обмін", "сервіс", "брак", "ремонт"],
            "програма лояльності та знижки": ["бонус", "знижк", "кешбек", "лояльніст", "промокод"],
            "бажання рекомендувати": ["рекоменду", "раджу", "друзям", "знайомим"],
        }

    def analyze_whole_text(self, review_text: str) -> dict:
        """Оцінює текст за всіма критеріями від 1 до 10."""
        results = {"text": review_text}
        text_lower = review_text.lower()
        
        # Розбиваємо текст на окремі речення для точного аналізу
        sentences = [s.strip() for s in re.split(r'[.!?\n]', review_text) if s.strip()]
        
        for aspect in self.aspects:
            if aspect == "загальне задоволення від покупки":
                # Для загального задоволення передаємо весь текст
                relevant_text = review_text
            else:
                # Збираємо тільки ті речення, де згадується конкретний критерій
                relevant_sentences = []
                for sentence in sentences:
                    sentence_lower = sentence.lower()
                    if any(kw in sentence_lower for kw in self.keywords.get(aspect, [])):
                        relevant_sentences.append(sentence)
                
                if not relevant_sentences:
                    results[aspect] = np.nan
                    continue
                    
                relevant_text = ". ".join(relevant_sentences)

            # 2. Якщо тема точно згадана — просимо модель оцінити емоцію
            # Формуємо текст у тому ж форматі, на якому навчали модель
            input_text = f"Критерій: {aspect}. Відгук: {relevant_text}"
            
            # Отримуємо ймовірності для всіх 4 класів
            probs = self.model.predict_proba([input_text])[0]
            
            # Ігноруємо probs[0] (Клас 0), оскільки ми вже знаємо, що тема згадана
            prob_neg = float(probs[1])
            prob_neu = float(probs[2])
            prob_pos = float(probs[3])
            
            total_sentiment = prob_neg + prob_neu + prob_pos
            if total_sentiment > 0:
                w_neg = prob_neg / total_sentiment
                w_neu = prob_neu / total_sentiment
                w_pos = prob_pos / total_sentiment
                
                score = (w_neg * 1.0) + (w_neu * 5.5) + (w_pos * 10.0)
                results[aspect] = round(score, 1)
            else:
                results[aspect] = np.nan
                
        return results

# Для швидкого тестування модуля окремо
if __name__ == "__main__":
    analyzer = PureNLPFeedbackAnalyzer()
    res = analyzer.analyze_whole_text("Крутий товар, але доставка підкачала. Зачекав 2 тижні.")
    print(res)
