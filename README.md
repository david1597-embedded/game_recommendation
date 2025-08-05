# 🎮게임 설명 기반 스팀 무료 게임 추천 시스템

<img width="1885" height="439" alt="image" src="https://github.com/user-attachments/assets/2907e941-2e40-4a25-a9be-716d1e9ba45f" />


> **Steam 게임 설명 및 자연어 처리 기반 콘텐츠 추천 시스템**\
> PyQt5를 활용한 GUI와 더불어 TF-IDF와 WordVec을 활용한 설명이 유사한 게임을 추천해주는 시스템

---

## 📌 Features

- 🔍 **게임 검색 & 추천**
  - 게임 제목 직접 입력 또는 드롭다운 목록에서 선택가능
  - 추천시마다 다른 게임들을 추천해주어 선택의 폭이 넓어짐
- 🧠 **추천 알고리즘**
  - TF-IDF와 Word2Vec을 활용한 콘텐츠 기반 추천. 게임 설명 기반으로 추천하여 비슷한 계열의 게임을 추천받을 수 있음
  - 상위 유사도 게임 중 무작위 5개 추천 → 매번 새로운 추천 조합 제공. 추천할때마다 똑같은 게임이 추천되지 않게하여 피로감을 줄여줆
- 🎥 **게임 미리보기**
  - 참조한 게임 & 추천 게임별 유튜브 미리보기 영상 제공
- 🛒 **Steam 바로가기**
  - 추천 게임 클릭 시 Steam 스토어 페이지로 이동해 찾지 않고 쉽게 구매를 가능하게함
 
---

## 🖥️ Screenshots

<img width="1211" height="660" alt="image" src="https://github.com/user-attachments/assets/5f00ccd6-b1bb-44ef-9bec-681e867e7dd2" />

직관적인 GUI로 사용자에게 편의성을 제공함

<p align="center">
  <img src="https://github.com/user-attachments/assets/9ba37f82-bfad-42ed-a47b-8d59e46ad541" width="49%" />
  <img src="https://github.com/user-attachments/assets/5a6f99b2-0e3c-4e40-96a9-6416fdcf3b5c" width="49%" />
</p>

---

## ⚙️ Installation

```
git clone https://github.com/david1597-embedded/game_recommendation.git
cd game_recommendation
```
### Windows

```
python -m venv venv
venv\Sciprts\activate
pip install -r requirements.py
python main.py
```
### Ubuntu
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.py
python main.py
```
