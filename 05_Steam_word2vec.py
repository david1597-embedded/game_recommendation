# TFIDF 는 문장을 벡터로 나눈거
# word2vec 는 단어를 벡터를 나누는거
import pandas as pd
from gensim.models import Word2Vec

df_description = pd.read_csv('./Crawling_data/steam_game_token.csv')


description = list(df_description['Description'])
print(df_description.iloc[0,0], description[0])
# NaN이나 숫자 제거하고 문자열로 변환


tokens = []
for sentence in description:
    token = sentence.split() # token = 형태소 들의 리스트
    tokens.append(token)
print(tokens[0:2])

embedding_model = Word2Vec(tokens, vector_size=100, window=4,  # window= 4개만 보고 학습시키는것
                           min_count=15, workers=4, epochs=100, sg=1) # min_count = 이정도 출현해야 학습하겠다 # workers = 시스템 코어 갯수
             # sg = 	학습 알고리즘 선택입니다. 1이면 Skip-gram, 0이면 CBOW입니다. Skip-gram은 드문 단어 학습에 강합니다.
embedding_model.save('./model/word2vec_steam.model')
print(list(embedding_model.wv.index_to_key))
print(len(embedding_model.wv.index_to_key))