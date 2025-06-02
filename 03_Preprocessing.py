import pandas as pd
import re
from konlpy.tag import Okt
from collections import Counter






# Okt 초기화
okt = Okt()

# 불용어 리스트
korean_stop_words = {'게임', '이다', '있다', '한다', '되다', '위해', '통해', '것', '수', '때', '더', '매우', '정말',
                     '아주', '하다', '당신', '플레이어', '플레이', '모든', '사용', '다른', '않다', '많다', '없다',
                     '다양하다', '새롭다', '되어다', '만들다', '사람', '가지', '자신', '대한', '우리', '시간', '가장'
                                                                                      '보다', '같다', '오다', '가다', '따르다',
                     '받다', '포함', '가능하다', '크다', '거나', '시작', '제공', '기능',
                     '시스템', '추가', '무료', '가장', '보다', '그것', '그녀', '아니다', '이상', '동안', '명의', '진행', '기반', '개발',
                     '목표', '방법', '모두', '최고', '하나', '모드', '맵', '아이템', '레벨', '스킬'}
english_stop_words = {'game', 'games', 'player', 'players', 'play', 'playing', 'the', 'a', 'an', 'and', 'or', 'but',
                      'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been',
                      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
                      'can', 'must', 'this', 'that', 'these', 'those', 'prologue', 'mode', 'map', 'item', 'level',
                      'skill'}

# 입력 파일 경로


input_file = r'D:\workplace\game_recommendation\Crawling_data\steam_game_translated.csv'

# CSV 파일 로드
try:
    df = pd.read_csv(input_file, encoding='utf-8')
except Exception as e:
    print(f"CSV 파일 로드 중 오류 발생: {e}")
    exit()

# 전처리
target_titles = ['皇帝', '生死狙击：战火重燃（国际版）']


target_df = df[df['Title'].isin(target_titles)].reset_index(drop=True)

# 확인
print(target_df)
df_description = pd.read_csv(input_file)
df_description.dropna(inplace=True)
df_description['Title'] = df_description['Title'].str.lower().str.strip()
df_description = df_description.drop_duplicates(subset=['Title'])

# 토큰화는 반드시 전처리 후에
tokens = [desc.split() for desc in df_description['Description']]


# tfidf_matrix도 이 df_description 기준으로 만들어졌다고 가정해야 함


def extract_korean_tokens(text):
    """한국어 토큰 추출"""
    korean_text = re.sub('[^가-힣\s]', ' ', text)
    if not korean_text.strip():
        return []

    try:
        tokened = okt.pos(korean_text, stem=True)
        df_token = pd.DataFrame(tokened, columns=['word', 'class'])
        df_token = df_token[df_token['class'].isin(['Noun', 'Adjective', 'Verb'])]
        words = [word for word in df_token['word']
                 if len(word) > 1 and word not in korean_stop_words]
        return words
    except:
        return []


def extract_english_tokens(text):
    """영어 토큰 추출 - 단순하고 확실한 방법"""
    # 영어만 추출
    english_text = re.sub('[^a-zA-Z\s]', ' ', text)
    if not english_text.strip():
        return []

    # 공백 기준으로 분할하고 소문자 변환
    words = english_text.lower().split()

    # 필터링: 3글자 이상, 불용어 제거, 순수 알파벳만
    filtered_words = []
    for word in words:
        word = word.strip()
        if (len(word) >= 3 and
                word not in english_stop_words and
                word.isalpha() and
                not word.isdigit()):
            filtered_words.append(word)

    return filtered_words


# 토큰화 및 전처리
cleaned_sentences = []
all_tokens = []

print("토큰화 진행 중...")
for idx, row in df.iterrows():
    # 1. Title과 Description 결합
    title = str(row['Title']).strip()
    description = str(row['Description'])  # NaN 방지
    combined_text = f"{title} {description}"

    # 2. 한국어 토큰 추출
    korean_tokens = extract_korean_tokens(combined_text)

    # 3. 영어 토큰 추출
    english_tokens = extract_english_tokens(combined_text)

    # 4. 토큰 결합
    all_words = korean_tokens + english_tokens

    # 디버깅: 처음 5개 항목만 출력
    if idx < 5:
        print(f"\n=== 항목 {idx + 1} ===")
        print(f"원문: {combined_text[:100]}...")
        print(f"한국어 토큰 ({len(korean_tokens)}개): {korean_tokens[:10]}")  # 처음 10개만
        print(f"영어 토큰 ({len(english_tokens)}개): {english_tokens[:10]}")  # 처음 10개만
        print(f"결합된 토큰: {(korean_tokens + english_tokens)[:15]}")  # 처음 15개만

    # 5. 전체 토큰 리스트에 추가 (빈도 분석용)
    all_tokens.extend(all_words)

    # 6. 클린 문장 생성
    cleaned_sentence = ' '.join(all_words)
    cleaned_sentences.append(cleaned_sentence)

print(f"\n총 {len(df)}개 항목 처리 완료")

# 7. 상위 20개 토큰 출력 (한국어/영어 구분)
token_counts = Counter(all_tokens)
print("\n상위 20개 토큰 (빈도순):")
for i, (word, count) in enumerate(token_counts.most_common(50), 1):
    lang = "한국어" if re.match('[가-힣]', word) else "영어"
    print(f"{i:2d}. {word} ({lang}): {count}")

# 8. 한국어/영어 토큰 통계
korean_tokens = [token for token in all_tokens if re.match('[가-힣]', token)]
english_tokens = [token for token in all_tokens if re.match('[a-zA-Z]', token)]

print(f"\n토큰 통계:")
print(f"전체 토큰 수: {len(all_tokens):,}")
print(f"한국어 토큰 수: {len(korean_tokens):,}")
print(f"영어 토큰 수: {len(english_tokens):,}")
print(f"고유 토큰 수: {len(set(all_tokens)):,}")

# 9. Title과 Cleaned_Description으로 DataFrame 생성
output_df = pd.DataFrame({
    'Title': df['Title'],
    'Description': cleaned_sentences
})

# 빈 토큰화 결과 확인 및 처리
empty_results = output_df[output_df['Description'].str.strip() == '']
if len(empty_results) > 0:
    print(f"\n주의: {len(empty_results)}개 항목에서 토큰화 결과가 비어있습니다.")
    print("비어있는 항목의 원본 Title:")
    for idx in empty_results.index[:5]:  # 처음 5개만 출력
        print(f"- {df.loc[idx, 'Title']}")

    # 빈 Description을 원본 Title로 대체
    print("\n빈 Description을 원본 Title로 대체중...")
    for idx in empty_results.index:
        original_title = str(df.loc[idx, 'Title'])

        # 특정 문제 제목들 처리
        if original_title == '皇帝':
            output_df.loc[idx, 'Description'] = 'emperor'
        elif original_title == '生死狙击：战火重燃（国际版）':
            output_df.loc[idx, 'Description'] = 'battle shooter game international'
        else:
            # 다른 빈 결과들도 원본 Title로 대체
            if original_title.strip() == '' or original_title == 'nan':
                output_df.loc[idx, 'Description'] = 'unknown title'
            else:
                # 원본 제목을 간단히 토큰화해서 사용
                simple_tokens = re.sub(r'[^\w\s]', ' ', original_title.lower()).split()
                processed_tokens = [token for token in simple_tokens if len(token) >= 2]
                if processed_tokens:
                    output_df.loc[idx, 'Description'] = ' '.join(processed_tokens)
                else:
                    output_df.loc[idx, 'Description'] = 'unknown title'

    print(f"✅ {len(empty_results)}개 항목 수정 완료!")

    # 수정 후 다시 확인
    remaining_empty = output_df[output_df['Description'].str.strip() == '']
    print(f"남은 빈 Description: {len(remaining_empty)}개")

# 10. 결과를 CSV로 저장
output_file = r'D:\workplace\game_recommendation\Crawling_data\steam_game_token.csv'
try:
    output_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"\n토큰화된 데이터가 {output_file}에 저장되었습니다.")
except Exception as e:
    print(f"CSV 파일 저장 중 오류 발생: {e}")

# 결과 미리보기
print("\n저장된 데이터 미리보기:")
print(output_df.head(3))