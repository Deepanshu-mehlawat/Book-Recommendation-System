from flask import Flask, jsonify, request, render_template
import pymongo
import random
import chatbot
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import numpy as np
from bson import ObjectId

app = Flask(__name__)

client = pymongo.MongoClient("mongodb+srv://adityabansal22cse:Aditya11@bookfair.vggamhp.mongodb.net/")
db = client["nbt"]
books_collection = db["booklistings"]
stalls_collection = db['stalls']
user_interactions_collection = db['user_interactions']

@app.route('/')
def home():
    return "Hi"


def get_recommendations_by_age_gender_category(age, gender, limit=10):
    age_group = (age // 10) * 10

    interactions = list(user_interactions_collection.find({'age': {'$gte': age_group, '$lt': age_group + 10}}))

    book_data = {}
    for interaction in interactions:
        book_id = interaction['book_id']
        clicks = interaction['clicks']
        interaction_gender = interaction['gender']

        if book_id not in book_data:
            book_data[book_id] = {'clicks_sum': 0, 'ge': 0, 'gne': 0}

        book_data[book_id]['clicks_sum'] += clicks
        if interaction_gender == gender:
            book_data[book_id]['ge'] += 1
        else:
            book_data[book_id]['gne'] += 1

    sorted_books = sorted(
        book_data.items(),
        key=lambda x: ((x[1]['ge'] + 1) / (x[1]['ge'] + x[1]['gne'] + 1), x[1]['clicks_sum']),
        reverse=True
    )

    recommended_books = []
    for book_id, data in sorted_books[:limit]:
        book_info = books_collection.find_one({'id': int(book_id)})
        if book_info:
            recommended_books.append(int(book_id))

    return recommended_books

@app.route('/top_clicks', methods=['GET'])
def top_clicks():
    user_id = request.args.get('user_id')
    favorite_genre = request.args.get('favorite_genre')
    age = request.args.get('age', type=int)
    gender = request.args.get('gender')

    if not all([user_id, favorite_genre, age, gender]):
        return jsonify({'error': 'Missing required query parameters'}), 400

    # Step 1: Get top books by favorite genre
    top_genre_books = list(books_collection.find({'Main_category': favorite_genre}, {'_id': 0, 'id': 1}).sort([('clicks', -1)]).limit(5))
    top_genre_book_ids = [book['id'] for book in top_genre_books]

    # Step 2: Get recommendations by age and gender
    age_gender_recommendations = get_recommendations_by_age_gender_category(age, gender, limit=5)
    
    # Combine and remove duplicates
    all_recommendations = list(set(top_genre_book_ids + age_gender_recommendations))

    # Step 3: Fill the remaining slots with the top clicked books if needed
    if len(all_recommendations) < 15:
        additional_books = list(books_collection.find(
            {'id': {'$nin': all_recommendations}}, {'_id': 0, 'id': 1}
        ).sort([('clicks', -1)]).limit(15 - len(all_recommendations)))
        all_recommendations.extend([book['id'] for book in additional_books])

    return jsonify({'top_books_by_clicks': all_recommendations[:15]})

@app.route('/stalls/<int:book_id>', methods=['GET'])
def stalls_by_book(book_id):
    # Find stalls related to the given book_id
    stalls = list(stalls_collection.find({'bookID': book_id}, {'_id': 0, 'stall_id': 1, 'IsAuthor': 1, 'stall_impressions': 1}))

    # Sort stalls by isAuthor (True first) and then by stall_impressions (descending)
    sorted_stalls = sorted(stalls, key=lambda x: (not x['IsAuthor'], -x['stall_impressions']))

    # Prepare JSON response with stall_id and rec flag (1 for isAuthor, 0 otherwise)
    response = [{'stall_id': stall['stall_id'], 'rec': 1 if stall['IsAuthor'] else 0} for stall in sorted_stalls]

    return jsonify({'stalls': response})

@app.route('/top_impressions', methods=['GET'])
def top_impressions():
    user_age = request.args.get('age', type=int)
    user_gender = request.args.get('gender')

    # Define the time range (e.g., last 7 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    # Determine the age group using (age // 10) * 10
    age_group = (user_age // 10) * 10
    
    # Step 1: Fetch interactions in the last 7 days for the specified age group and gender
    filter_query = {
        'createdAt': {'$gte': start_date, '$lt': end_date},
        'age': {'$gte': age_group, '$lt': age_group + 10}
    }
    if user_gender:
        filter_query['gender'] = user_gender
    
    recent_interactions = user_interactions_collection.find(filter_query)

    # Step 2: Aggregate clicks and impressions for each book
    trending_data = {}
    for interaction in recent_interactions:
        book_id = interaction['book_id']
        clicks = interaction.get('clicks', 0)
        impressions = books_collection.find_one({'id': int(book_id)}).get('impressions', 0)
        
        if book_id not in trending_data:
            trending_data[book_id] = {'clicks': 0, 'impressions': 0}
        
        trending_data[book_id]['clicks'] += clicks
        trending_data[book_id]['impressions'] += impressions
    
    # Step 3: Sort books by trending score (clicks + impressions)
    sorted_books = sorted(trending_data.items(), key=lambda x: x[1]['clicks'] + x[1]['impressions'], reverse=True)
    
    # Step 4: Get top 15 trending books
    top_trending_books = []
    for book_id, data in sorted_books:
        if len(top_trending_books) >= 15:
            break
        if book_id not in top_trending_books:
            top_trending_books.append(int(book_id))  # Convert book_id to int
    
    # Step 5: If less than 15 books, fill with highest impression books
    if len(top_trending_books) < 15:
        additional_books = list(books_collection.find(
            {'id': {'$nin': top_trending_books}}, {'_id': 0, 'id': 1}
        ).sort([('impressions', -1)]).limit(15 - len(top_trending_books)))
        top_trending_books.extend([book['id'] for book in additional_books])
    
    return jsonify({'top_books_by_impressions': top_trending_books})

def calculate_similarity(search_term, text):
    matcher = SequenceMatcher(None, search_term.lower(), text.lower())
    return matcher.ratio()

@app.route('/search', methods=['GET', 'POST'])
def search_books():
    search_term = ''
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'search_term' not in data:
            return jsonify({'error': 'Missing search term in request data'}), 400
        search_term = data['search_term']
    else:  # GET request
        search_term = request.args.get('search_term')
        if not search_term:
            return jsonify({'error': 'Missing search term in request data'}), 400

    books = get_top_books(search_term)
    return jsonify({'books': books})


WORDS_TO_REMOVE = {"search", "find", "book","books","by","on", "available","want","fair","bookfair","written","category","genre","recommend","suggest"}

def clean_message(message):
    words = message.split()
    cleaned_words = [word for word in words if word.lower() not in WORDS_TO_REMOVE]
    return ' '.join(cleaned_words)

@app.route('/chat', methods=['POST'])
def chat():
  if request.method == 'POST':
    data = request.get_json()
    if not data or 'message' not in data:
      return jsonify({'error': 'Missing message in request data'}), 400
    user_message = data['message'].lower()

    # Call methods from chatbot.py to process the message
    intents = chatbot.predict_class(user_message)
    response = chatbot.get_response(intents, chatbot.intents)
    if response == 'Searching':
        # Get the top 5 books based on the search string (user message)
        cleaned_message = clean_message(user_message)
        top_books = get_top_books(cleaned_message)
        return jsonify({'response': "Your search results are here", 'action': 2, 'data': top_books})
    elif response == 'booking':
        return jsonify({'response': response,'action':1})
    return jsonify({'response': response,'action':0})
  else:
    return jsonify({'error': 'Invalid request method'}), 405

def get_top_books(search_term):
    # Exact match search in title
    title_matches = list(books_collection.find(
        {'Title': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}
    ).sort('clicks', -1))

    # Exact match search in authors
    author_matches = list(books_collection.find(
        {'Authors': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}
    ).sort('clicks', -1))

    # Exact match search in category
    category_matches = list(books_collection.find(
        {'Category': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}
    ).sort('clicks', -1))

    # Combine exact matches in the specified order without duplicates
    exact_matches = title_matches + \
                    [match for match in author_matches if match not in title_matches] + \
                    [match for match in category_matches if match not in title_matches and match not in author_matches]

    if len(exact_matches) >= 5:
        # Ensure the 'id' field is an integer
        for match in exact_matches:
            match['id'] = int(match['id'])
        return exact_matches[:5]

    # If fewer than 5 exact matches, find similar books
    all_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'Title': 1, 'Authors': 1, 'Category': 1, 'clicks': 1}))
    similarity_scores = [
        (
            max(
                calculate_similarity(search_term, book['Title']),
                calculate_similarity(search_term, book['Authors']),
                calculate_similarity(search_term, book['Category'])
            ),
            book
        )
        for book in all_books
    ]

    # Sort by similarity score in descending order
    similarity_scores.sort(key=lambda x: x[0], reverse=True)

    # Combine exact matches with the top similar books, ensuring no duplicates
    combined_results = exact_matches + [score[1] for score in similarity_scores if score[1] not in exact_matches]

    # Ensure the 'id' field is an integer
    for result in combined_results:
        result['id'] = int(result['id'])

    return combined_results[:5]


def get_top_authors():
    # Aggregation pipeline to find top 5 authors based on clicks
    pipeline = [
        {"$group": {"_id": "$Authors", "total_clicks": {"$sum": "$clicks"}}},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 5}
    ]
    return list(books_collection.aggregate(pipeline))

@app.route('/top_authors', methods=['GET'])
def suggest_books():
    try:
        top_authors = get_top_authors()
        suggestions = []

        for author in top_authors:
            author_name = author['_id']
            # Query without _id field in projection
            books = list(books_collection.find({"Authors": author_name}, {"_id": 0, "id": 1, "Title": 1, "Authors": 1, "Category": 1}).limit(5))
            suggestions.extend(books[:5])  # Add up to 5 books per author
        
        return jsonify(suggestions[:5])

    except Exception as e:
        print(f"Error in /top_authors endpoint: {str(e)}")
        print(f"Contents of suggestions list: {suggestions}")
        return jsonify({'error': 'An error occurred. Please try again later.'}), 500


def get_top_publishers():
    # Aggregation pipeline to find top 5 publishers based on clicks
    pipeline = [
        {"$group": {"_id": "$Publisher", "total_clicks": {"$sum": "$clicks"}}},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 5}
    ]
    return list(books_collection.aggregate(pipeline))

@app.route('/top_publishers', methods=['GET'])
def suggest_books_by_publishers():
    try:
        top_publishers = get_top_publishers()
        suggestions = []

        for publisher in top_publishers:
            publisher_name = publisher['_id']
            # Query without _id field in projection
            books = list(books_collection.find({"Publisher": publisher_name}, {"_id": 0, "id": 1, "Title": 1, "Authors": 1, "Publisher": 1, "Category": 1}).limit(5))
            suggestions.extend(books[:5])  # Add up to 5 books per publisher
        
        return jsonify(suggestions[:5])

    except Exception as e:
        print(f"Error in /top_publishers endpoint: {str(e)}")
        print(f"Contents of suggestions list: {suggestions}")
        return jsonify({'error': 'An error occurred. Please try again later.'}), 500


if __name__ == '__main__':
    app.run(debug=True)
