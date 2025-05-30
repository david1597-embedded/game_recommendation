import asyncio
import pandas as pd
from googletrans import Translator
from langdetect import detect
import time

async def translate_texts():
    translator = Translator()
    df = pd.read_csv('./Crawling_data/steam_game.csv')
    print("✅ 원본 개수:", len(pd.read_csv('./Crawling_data/steam_game.csv')))
    df.dropna(subset=['Title', 'Description'], inplace=True)
    df['Description'] = df['Description'].str.replace('게임 정보', '', regex=False).str.strip()
    df['Title'] = df['Title'].astype(str).str.strip().str.lower().str.replace(r'\s+', ' ', regex=True)
    df = df.drop_duplicates(subset=['Title'])


    print("✅ 전처리 후 개수:", len(df))

    translated_descriptions = []
    target_langs = ['en', 'ja', 'zh-cn', 'zh-tw' , 'zh']

    for count, (_, row) in enumerate(df.iterrows(), start=1):
        original_text = str(row['Description'])
        try:
            lang = detect(original_text)
        except:
            lang = 'unknown'

        if lang in target_langs:
            try:
                translated = await translator.translate(original_text, src=lang, dest='ko')
                print(f"[{count}] 번역됨 ({lang} → ko): {translated.text[:60]}...")
                translated_descriptions.append(translated.text)
            except Exception as e:
                print(f"[{count}] 번역 실패 ({lang}): {e}")
                translated_descriptions.append(original_text)
        else:
            print(f"[{count}] 번역 생략 ({lang})")
            translated_descriptions.append(original_text)

        time.sleep(0.1)

    df['Description'] = translated_descriptions
    df.to_csv('./Crawling_data/steam_game_translated.csv', index=False, encoding='utf-8-sig')
    print("✅ 완료! 번역 + 중복 제거된 데이터 저장")

asyncio.run(translate_texts())
