import streamlit as st
import pickle
import requests
import os


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Movie Recommendation System",
    page_icon="🎬",
    layout="wide"
)


# =========================================================
# TMDB API KEY
# =========================================================
#
# Easiest option for your project:
#
# API_KEY = "YOUR_NEW_TMDB_API_KEY"
#
# Better option:
# Set environment variable TMDB_API_KEY
#
# Windows:
# set TMDB_API_KEY=YOUR_NEW_TMDB_API_KEY
#
# =========================================================

API_KEY = "d8e466aee4f31335b6be6b3c04a5606e"

# =========================================================
# LOAD DATA
# =========================================================

try:

    with open("movies.pkl", "rb") as f:
        movies = pickle.load(f)

    with open("similarity.pkl", "rb") as f:
        similarity = pickle.load(f)

except FileNotFoundError:

    st.error(
        "movies.pkl or similarity.pkl was not found. "
        "Make sure both files are in the same folder as app.py."
    )

    st.stop()


# =========================================================
# TMDB SESSION
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "MovieRecommendationSystem/1.0"
})


# =========================================================
# TMDB REQUEST
# =========================================================

def tmdb_request(endpoint, params=None):

    if not API_KEY or API_KEY == "YOUR_NEW_TMDB_API_KEY":
        return None

    if params is None:
        params = {}

    params["api_key"] = API_KEY
    params["language"] = "en-US"

    try:

        response = session.get(
            f"https://api.themoviedb.org/3/{endpoint}",
            params=params,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()

        print(
            "TMDB Error:",
            response.status_code,
            response.text
        )

        return None

    except requests.exceptions.RequestException as e:

        print("TMDB Connection Error:", e)

        return None


# =========================================================
# GET MOVIE DETAILS
# =========================================================

def get_movie_details(movie_id, title):

    result = {
        "title": title,
        "poster": None,
        "rating": "N/A",
        "release": "N/A",
        "genres": "N/A",
        "overview": "Overview not available."
    }


    # -----------------------------------------------------
    # METHOD 1
    # Try TMDB using movie ID
    # -----------------------------------------------------

    data = None

    try:

        data = tmdb_request(
            f"movie/{int(movie_id)}",
            {
                "append_to_response": ""
            }
        )

    except Exception as e:

        print("Movie ID error:", e)


    # -----------------------------------------------------
    # METHOD 2
    # If ID fails, search by title
    # -----------------------------------------------------

    if not data:

        search_data = tmdb_request(
            "search/movie",
            {
                "query": title,
                "include_adult": False
            }
        )

        if search_data and search_data.get("results"):

            results = search_data["results"]

            selected = None

            # Exact title match
            for movie in results:

                if (
                    movie.get("title", "").strip().lower()
                    == title.strip().lower()
                ):

                    selected = movie
                    break

            # If exact match not found
            if selected is None:

                selected = results[0]

            data = selected


    # -----------------------------------------------------
    # If TMDB returned nothing
    # -----------------------------------------------------

    if not data:
        return result


    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    result["title"] = data.get("title", title)


    # -----------------------------------------------------
    # POSTER
    # -----------------------------------------------------

    poster_path = data.get("poster_path")

    if poster_path:

        result["poster"] = (
            "https://image.tmdb.org/t/p/w500"
            + poster_path
        )


    # -----------------------------------------------------
    # RATING
    # -----------------------------------------------------

    rating = data.get("vote_average")

    if rating is not None:

        try:
            result["rating"] = round(float(rating), 1)

        except:
            result["rating"] = "N/A"


    # -----------------------------------------------------
    # RELEASE DATE
    # -----------------------------------------------------

    release = data.get("release_date")

    if release:
        result["release"] = release


    # -----------------------------------------------------
    # OVERVIEW
    # -----------------------------------------------------

    overview = data.get("overview")

    if overview:
        result["overview"] = overview


    # -----------------------------------------------------
    # GENRES
    # -----------------------------------------------------

    genres = data.get("genres")

    if genres:

        result["genres"] = ", ".join(
            genre.get("name", "")
            for genre in genres
            if genre.get("name")
        )


    # -----------------------------------------------------
    # SEARCH RESULT MAY NOT HAVE GENRES
    # Get full details if necessary
    # -----------------------------------------------------

    if (
        result["genres"] == "N/A"
        and data.get("id")
    ):

        detail_data = tmdb_request(
            f"movie/{int(data['id'])}"
        )

        if detail_data:

            genres = detail_data.get("genres")

            if genres:

                result["genres"] = ", ".join(
                    genre.get("name", "")
                    for genre in genres
                    if genre.get("name")
                )


            # Poster fallback

            if not result["poster"]:

                poster_path = detail_data.get(
                    "poster_path"
                )

                if poster_path:

                    result["poster"] = (
                        "https://image.tmdb.org/t/p/w500"
                        + poster_path
                    )


            # Overview fallback

            if (
                result["overview"]
                == "Overview not available."
            ):

                overview = detail_data.get("overview")

                if overview:
                    result["overview"] = overview


            # Rating fallback

            if result["rating"] == "N/A":

                rating = detail_data.get(
                    "vote_average"
                )

                if rating is not None:

                    try:
                        result["rating"] = round(
                            float(rating), 1
                        )

                    except:
                        pass


            # Release fallback

            if result["release"] == "N/A":

                release = detail_data.get(
                    "release_date"
                )

                if release:
                    result["release"] = release


    return result


# =========================================================
# RECOMMENDATION FUNCTION
# =========================================================

def recommend(movie_title, number_of_movies=5):

    # -----------------------------------------------------
    # Find selected movie
    # -----------------------------------------------------

    movie_rows = movies[
        movies["title"].astype(str).str.lower()
        == movie_title.lower()
    ]


    if movie_rows.empty:
        return []


    movie_index = movie_rows.index[0]


    # -----------------------------------------------------
    # Get similarity scores
    # -----------------------------------------------------

    distances = similarity[movie_index]


    # -----------------------------------------------------
    # Sort by similarity
    # -----------------------------------------------------

    movie_list = sorted(
        list(enumerate(distances)),
        reverse=True,
        key=lambda x: x[1]
    )


    recommendations = []


    # -----------------------------------------------------
    # Get more candidates than needed
    # This helps skip duplicates
    # -----------------------------------------------------

    for index, score in movie_list[1:40]:

        if len(recommendations) >= number_of_movies:
            break


        movie = movies.iloc[index]

        title = str(movie["title"])


        # -------------------------------------------------
        # Avoid duplicate titles
        # -------------------------------------------------

        duplicate = any(
            item["title"].lower()
            == title.lower()
            for item in recommendations
        )

        if duplicate:
            continue


        # -------------------------------------------------
        # Movie ID
        # -------------------------------------------------

        try:

            movie_id = int(movie["movie_id"])

        except:

            continue


        # -------------------------------------------------
        # Get TMDB details
        # -------------------------------------------------

        details = get_movie_details(
            movie_id,
            title
        )


        details["title"] = title


        # -------------------------------------------------
        # Similarity percentage
        # -------------------------------------------------

        details["similarity"] = round(
            float(score) * 100,
            1
        )


        recommendations.append(details)


    return recommendations


# =========================================================
# USER INTERFACE
# =========================================================

st.title("🎬 Movie Recommendation System")

st.write(
    "Find movies similar to your favourite movie."
)


# =========================================================
# MOVIE SELECTION
# =========================================================

movie_titles = (
    movies["title"]
    .dropna()
    .astype(str)
    .tolist()
)

selected_movie = st.selectbox(
    "Choose a Movie",
    movie_titles
)


# =========================================================
# RECOMMEND BUTTON
# =========================================================

if st.button("🎥 Recommend Movies"):

    with st.spinner(
        "Finding similar movies..."
    ):

        recommendations = recommend(
            selected_movie,
            number_of_movies=5
        )


    if not recommendations:

        st.error(
            "Sorry, no recommendations could be found."
        )


    else:

        st.subheader(
            "Recommended Movies"
        )


        # -------------------------------------------------
        # FIVE COLUMNS
        # -------------------------------------------------

        cols = st.columns(5)


        for col, movie in zip(
            cols,
            recommendations
        ):

            with col:


                # =========================================
                # POSTER
                # =========================================

                if movie["poster"]:

                    try:

                        st.image(
                            movie["poster"],
                            width=180
                        )

                    except Exception:

                        st.markdown(
                            """
                            <div style="
                                height:270px;
                                display:flex;
                                align-items:center;
                                justify-content:center;
                                background:#262730;
                                border-radius:10px;
                                color:#AAAAAA;
                                text-align:center;
                            ">
                                🎬<br>
                                Poster Not Available
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                else:

                    st.markdown(
                        """
                        <div style="
                            height:270px;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            background:#262730;
                            border-radius:10px;
                            color:#AAAAAA;
                            text-align:center;
                        ">
                            🎬<br>
                            Poster Not Available
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # =========================================
                # TITLE
                # =========================================

                st.markdown(
                    f"### {movie['title']}"
                )


                # =========================================
                # SIMILARITY
                # =========================================

                if movie["similarity"] is not None:

                    st.write(
                        f"🎯 Similarity: "
                        f"{movie['similarity']}%"
                    )


                # =========================================
                # RATING
                # =========================================

                st.write(
                    f"⭐ Rating: "
                    f"{movie['rating']}"
                )


                # =========================================
                # RELEASE
                # =========================================

                st.write(
                    f"📅 Release: "
                    f"{movie['release']}"
                )


                # =========================================
                # GENRES
                # =========================================

                st.write(
                    f"🎭 {movie['genres']}"
                )


                # =========================================
                # OVERVIEW
                # =========================================

                overview = movie["overview"]


                if len(overview) > 150:

                    overview = (
                        overview[:150]
                        + "..."
                    )


                st.caption(overview)


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "🎬 Movie Recommendation System | "
    "Powered by TMDB"
)