from flask import Flask, jsonify, request, render_template
import pymongo
import random
import chatbot
from difflib import SequenceMatcher
import numpy as np

app = Flask(__name__)

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["Books_db"]
books_collection = db["Books"]
stalls_collection = db['Stalls']

def calculate_similarity(search_term, text):
    matcher = SequenceMatcher(None, search_term.lower(), text.lower())
    return matcher.ratio()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/stalls/<int:book_id>', methods=['GET'])
def stalls_by_book(book_id):
    # Find stalls related to the given book_id
    stalls = list(stalls_collection.find({'bookID': book_id}, {'_id': 0, 'stall_id': 1, 'IsAuthor': 1, 'stall_impressions': 1}))

    # Sort stalls by isAuthor (True first) and then by stall_impressions (descending)
    sorted_stalls = sorted(stalls, key=lambda x: (not x['IsAuthor'], -x['stall_impressions']))

    # Prepare JSON response with stall_id and rec flag (1 for isAuthor, 0 otherwise)
    response = [{'stall_id': stall['stall_id'], 'rec': 1 if stall['IsAuthor'] else 0} for stall in sorted_stalls]

    return jsonify({'stalls': response})

@app.route('/top_clicks', methods=['GET'])
def top_clicks():
    top_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'clicks': 1}).sort([('clicks', -1)]).limit(5))
    top_book_ids = [book['id'] for book in top_books]
    return jsonify({'top_books_by_clicks': top_book_ids})

@app.route('/top_impressions', methods=['GET'])
def top_impressions():
    top_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'impressions': 1}).sort([('impressions', -1)]).limit(5))
    top_book_ids = [book['id'] for book in top_books]
    return jsonify({'top_books_by_impressions': top_book_ids})

@app.route('/search', methods=['GET', 'POST'])
def search_books():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'search_term' not in data:
            return jsonify({'error': 'Missing search term in request data'}), 400
        search_term = data['search_term']
    else:  # GET request
        search_term = request.args.get('search_term')
        if not search_term:
            return jsonify({'error': 'Missing search term in request data'}), 400

    # Fetch all books for percentile calculations
    all_books = list(books_collection.find({}, {'_id': 0, 'impressions': 1, 'clicks': 1}))
    impressions_values = [book.get('impressions', 0) for book in all_books]
    clicks_values = [book.get('clicks', 0) for book in all_books]

    # Calculate 75th percentile for impressions and clicks
    impressions_75th_percentile = np.percentile(impressions_values, 75)
    clicks_75th_percentile = np.percentile(clicks_values, 75)

    def get_rec_flag(book):
        impressions = book.get('impressions', 0)
        clicks = book.get('clicks', 0)
        if clicks > clicks_75th_percentile:
            return 2
        elif impressions > impressions_75th_percentile:
            return 1
        else:
            return 0

    # Search for exact matches in title
    title_exact_matches = list(books_collection.find(
        {'Title': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'impressions': 1, 'clicks': 1}
    ))

    # Sort by impressions
    title_exact_matches.sort(key=lambda x: x['impressions'], reverse=True)

    # If fewer than 5 exact matches, find similar titles
    title_similarities = []
    if len(title_exact_matches) < 5:
        books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'Title': 1, 'impressions': 1, 'clicks': 1}))
        title_similarities = [(calculate_similarity(search_term, book['Title']), book['id'], book['Title'], book['impressions'], book['clicks']) for book in books]
        title_similarities.sort(reverse=True, key=lambda x: x[0])  # Sort by highest similarity first

    top_results = title_exact_matches + [
        {'id': book_id, 'Title': title, 'impressions': impressions, 'clicks': clicks}
        for _, book_id, title, impressions, clicks in title_similarities[:max(0, 5 - len(title_exact_matches))]
    ]

    # Search for exact matches in authors
    author_exact_matches = list(books_collection.find(
        {'Authors': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'impressions': 1, 'clicks': 1}
    ))

    author_exact_matches.sort(key=lambda x: x['impressions'], reverse=True)

    # If fewer than 3 exact matches, find similar authors
    author_similarities = []
    if len(author_exact_matches) < 3:
        books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'Authors': 1, 'Title': 1, 'impressions': 1, 'clicks': 1}))
        author_similarities = [(calculate_similarity(search_term, book['Authors']), book['id'], book['Title'], book['impressions'], book['clicks']) for book in books]
        author_similarities.sort(reverse=True, key=lambda x: x[0])  # Sort by highest similarity first

    top_results.extend(
        author_exact_matches + [
            {'id': book_id, 'Title': title, 'impressions': impressions, 'clicks': clicks}
            for _, book_id, title, impressions, clicks in author_similarities[:max(0, 3 - len(author_exact_matches))]
        ]
    )

    # Search for exact matches in categories (genres)
    genre_exact_matches = list(books_collection.find(
        {'Category': {'$regex': search_term, '$options': 'i'}},
        {'_id': 0, 'id': 1, 'Title': 1, 'impressions': 1, 'clicks': 1}
    ))

    genre_exact_matches.sort(key=lambda x: x['impressions'], reverse=True)

    # If fewer than 2 exact matches, find similar categories
    genre_similarities = []
    if len(genre_exact_matches) < 2:
        books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'Category': 1, 'Title': 1, 'impressions': 1, 'clicks': 1}))
        genre_similarities = [(calculate_similarity(search_term, book['Category']), book['id'], book['Title'], book['impressions'], book['clicks']) for book in books]
        genre_similarities.sort(reverse=True, key=lambda x: x[0])  # Sort by highest similarity first

    top_results.extend(
        genre_exact_matches + [
            {'id': book_id, 'Title': title, 'impressions': impressions, 'clicks': clicks}
            for _, book_id, title, impressions, clicks in genre_similarities[:max(0, 3 - len(genre_exact_matches))]
        ]
    )

    # Remove duplicates and add "rec" flag
    seen = set()
    unique_results = []
    for book in top_results:
        if book['id'] not in seen:
            book['rec'] = get_rec_flag(book)
            unique_results.append(book)
            seen.add(book['id'])

    return jsonify({'books': unique_results})

@app.route('/chat', methods=['POST'])
def chat():
  if request.method == 'POST':
    data = request.get_json()
    if not data or 'message' not in data:
      return jsonify({'error': 'Missing message in request data'}), 400
    user_message = data['message']

    # Call methods from chatbot.py to process the message
    intents = chatbot.predict_class(user_message)
    response = chatbot.get_response(intents, chatbot.intents)
    if response == 'Searching':
        return jsonify({'response': response,'action':2})
    elif response == 'booking':
        return jsonify({'response': response,'action':1})
    return jsonify({'response': response,'action':0})
  else:
    return jsonify({'error': 'Invalid request method'}), 405


def get_top_authors():
    # Aggregation pipeline to find top 5 authors based on clicks
    pipeline = [
        {"$group": {"_id": "$Authors", "total_clicks": {"$sum": "$clicks"}}},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 5}
    ]
    return list(books_collection.aggregate(pipeline))

def get_random_book_id_by_author(author):
    books = list(books_collection.find({"Authors": author}, {"id": 1}))
    if books:
        book = random.choice(books)
        if book:
            return str(book["id"])  # Convert ObjectId to string
    return None

@app.route('/top_authors', methods=['GET'])
def suggest_books():
    top_authors = get_top_authors()
    suggestions = []

    for author in top_authors:
        book_id = get_random_book_id_by_author(author['_id'])  # Use '_id' here
        if book_id:
            suggestions.append(book_id)
    
    return jsonify(suggestions)


if __name__ == '__main__':
    app.run(debug=True)
