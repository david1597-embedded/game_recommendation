import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gensim.models import Word2Vec
from scipy.io import mmread
import pickle
import os

# ================================
# [1] 경로 설정 (유지보수 편의성 ↑)
# ================================
BASE_PATH = 'D:/workplace/game_recommendation'
DATA_FILE = os.path.join(BASE_PATH, 'Crawling_data//steam_game_translated.csv')
TFIDF_MODEL_FILE = os.path.join(BASE_PATH, 'model/tfidf_steam.pickle')
TFIDF_MATRIX_FILE = os.path.join(BASE_PATH, 'model/tfidf_steam.mtx')
W2V_MODEL_FILE = os.path.join(BASE_PATH, 'model/word2vec_steam.model')

# ================================
# [2] 데이터 및 모델 로딩
# ================================
try:
    df_description = pd.read_csv(DATA_FILE)
    tokens = [desc.split() for desc in df_description['Description']]
except Exception as e:
    print(f"데이터 파일 로드 실패: {e}")
    exit()

try:
    with open(TFIDF_MODEL_FILE, 'rb') as f:
        tfidf = pickle.load(f)
    tfidf_matrix = mmread(TFIDF_MATRIX_FILE).tocsr()
except Exception as e:
    print(f"TF-IDF 모델 로드 실패: {e}")
    exit()

try:
    w2v_model = Word2Vec.load(W2V_MODEL_FILE)
    print(f"✅ Word2Vec 모델 로드 완료 (벡터 크기: {w2v_model.vector_size})")
except Exception as e:
    print(f"Word2Vec 모델 로드 실패: {e}")
    exit()

# ================================
# [3] 문장 벡터 생성 함수 (가중 평균)
# ================================
def get_weighted_sentence_vector(tokens, model, tfidf_vectorizer):
    vec = np.zeros(model.vector_size)
    weight_sum = 0
    for token in tokens:
        if token in model.wv and token in tfidf_vectorizer.vocabulary_:
            weight = tfidf_vectorizer.idf_[tfidf_vectorizer.vocabulary_[token]]
            vec += model.wv[token] * weight
            weight_sum += weight
    return vec / weight_sum if weight_sum > 0 else vec

# ================================
# [4] 추천 함수 (인덱스 기반)
# ================================
def recommend_games_by_index(ref_idx, top_n=5):
    if not (0 <= ref_idx < len(df_description)):
        return f"❌ Error: 유효하지 않은 인덱스입니다 (0 ~ {len(df_description)-1})"

    game_title = df_description.iloc[ref_idx]['Title']
    print(f"\n🎮 기준 게임: {game_title} (인덱스 {ref_idx})")

    # TF-IDF 기반 유사도
    tfidf_ref = tfidf_matrix[ref_idx]
    tfidf_sim = cosine_similarity(tfidf_ref, tfidf_matrix)[0]

    # Word2Vec 기반 유사도
    ref_vector = get_weighted_sentence_vector(tokens[ref_idx], w2v_model, tfidf)
    all_vectors = np.array([get_weighted_sentence_vector(tok, w2v_model, tfidf) for tok in tokens])
    w2v_sim = cosine_similarity([ref_vector], all_vectors)[0]

    # 결합 유사도 (가중치 조절 가능)
    combined_sim = 0.7 * tfidf_sim + 0.3 * w2v_sim
    similar_indices = combined_sim.argsort()[::-1][1:top_n+1]

    recommendations = []
    for idx in similar_indices:
        recommendations.append({
            'Title': df_description.iloc[idx]['Title'],
            'Similarity': combined_sim[idx],
            'Description': df_description.iloc[idx]['Description'][:100] + "..."
        })
    return recommendations

# ================================
# [5] 추천 함수 (게임 제목 기반)
# ================================
def recommend_games_by_title(game_title, top_n=5):
    matches = df_description[df_description['Title'].str.lower() == game_title.lower()]
    if matches.empty:
        return f"❌ Error: '{game_title}'을(를) 찾을 수 없습니다."
    return recommend_games_by_index(matches.index[0], top_n)

# ================================
# [6] 테스트 실행
# ================================
if __name__ == "__main__":
    test_idx = 2
    result = recommend_games_by_index(test_idx)
    if isinstance(result, str):
        print(result)
    else:
        for rec in result:
            print(f"- {rec['Title']} | 유사도: {rec['Similarity']:.4f}")
            print(f"  설명: {rec['Description']}")
