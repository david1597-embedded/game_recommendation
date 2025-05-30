#TFIDF = (term frequency-inverse document frequency)란
#코퍼스(corpus, 문서집합)에서 한 단어가 얼마나 중요한지를 수치적으로 나타낸 가중치
import pickle

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.io import mmwrite, mmread






df_description = pd.read_csv('./Crawling_data/steam_game_token.csv')
df_description.dropna(inplace=True)
df_description.to_csv('./Crawling_data/steam_game_token.csv', index=False)

df_description.info()

df_description = pd.read_csv('./Crawling_data//steam_game_token.csv')

tfidf = TfidfVectorizer(sublinear_tf=True)
tfidf_matrix = tfidf.fit_transform(df_description['Description'])
print(tfidf_matrix.shape)
print(tfidf_matrix[0])

with open('./model/tfidf_steam.pickle', 'wb') as f:
    pickle.dump(tfidf, f)

mmwrite('./model/tfidf_steam.mtx', tfidf_matrix)       # matrix 저장할때 사용
