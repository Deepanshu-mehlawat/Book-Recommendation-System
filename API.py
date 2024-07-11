from flask import Flask, jsonify, request, render_template
import pymongo
import random
import chatbot
from difflib import SequenceMatcher
import numpy as np
from bson import ObjectId

app = Flask(__name__)

client = pymongo.MongoClient("mongodb+srv://adityabansal22cse:Aditya11@bookfair.vggamhp.mongodb.net/")
db = client["nbt"]
books_collection = db["booklistings"]
stalls_collection = db['stalls']
user_collection = db['users']
user_interactions_collection = db['user_interactions']  # Renamed to avoid variable name collision
age=0
gender=0

@app.route('/')
def home():
    return "Hi"


def get_age_and_gender(user_id):
    if user_id == '0':
        return None, None  # If user_id is '0', return None for age and gender
    
    user_data = user_collection.find_one({'_id': ObjectId(user_id)}, {'_id': 0, 'age': 1, 'gender': 1})
    if user_data:
        return user_data.get('age'), user_data.get('gender')
    else:
        return None, None

def get_age_group(age):
    if age is None or age < 0 or age > 100:
        return None
    return [(x, x + 10) for x in range(0, 100, 10) if x <= age < x + 10][0]

def get_recommendations_by_age_gender_category(age, gender, most_clicked_category, limit=25):
    age_group = get_age_group(age)
    
    if not age_group:
        return []
    print(age_group)
    # Step 1: Fetch interactions for users in the specified age group
    interactions = list(user_interactions_collection.find({
        'age': {'$gte': age_group[0], '$lte': age_group[1]}
    }))
    
    # Step 2: Aggregate data to calculate clicks_sum, ge, gne for each book_id
    books_aggregated = {}
    for interaction in interactions:
        book_id = interaction['book_id']
        clicks = interaction['clicks']
        interaction_gender = interaction['gender']
        
        if book_id not in books_aggregated:
            books_aggregated[book_id] = {
                'clicks_sum': 0,
                'ge': 0,
                'gne': 0
            }
        
        books_aggregated[book_id]['clicks_sum'] += clicks
        if interaction_gender == gender:
            books_aggregated[book_id]['ge'] += 1
        else:
            books_aggregated[book_id]['gne'] += 1
    
    # Step 3: Calculate gender_ratio and prepare list of dictionaries for sorting
    books_to_sort = []
    for book_id, data in books_aggregated.items():
        clicks_sum = data['clicks_sum']
        ge = data['ge']
        gne = data['gne']
        
        if ge + gne == 0:
            gender_ratio = 0  # Handle division by zero scenario
        else:
            gender_ratio = (ge + 1) / (ge + gne + 1)
        
        books_to_sort.append({
            'id': book_id,
            'clicks_sum': clicks_sum,
            'gender_ratio': gender_ratio
        })
    
    # Step 4: Sort books_to_sort by gender_ratio (descending) and clicks_sum (descending)
    sorted_books = sorted(books_to_sort, key=lambda x: (x['gender_ratio'], x['clicks_sum']), reverse=True)
    
    # Step 5: Lookup book_info from booklistings collection
    recommended_books = []
    for book in sorted_books[:limit]:
        book_info = books_collection.find_one({'id': int(book['id'])})
        if book_info:
            recommended_books.append({
                'id': int(book['id']),
                'category': book_info['Category']
            })
    return recommended_books

@app.route('/top_clicks', methods=['GET'])
def top_clicks():
    user_id = request.args.get('user_id', '0')  # Default to '0' if not provided
    user_age, user_gender = get_age_and_gender(user_id)
    print(user_age,user_gender)
    if user_age is None or user_gender is None:
        # If age or gender is not found, or user_id is '0', fall back to top books by clicks
        top_books = list(books_collection.find({}, {'_id': 0, 'id': 1}).sort([('clicks', -1)]).limit(25))
        top_book_ids = [book['id'] for book in top_books]
        return jsonify({'top_books_by_clicks': top_book_ids})
    
    user_interactions = list(user_interactions_collection.find({'user_id': user_id}))
    
    if not user_interactions:
        # No user interactions, fall back to top books by clicks
        top_books = list(books_collection.find({}, {'_id': 0, 'id': 1}).sort([('clicks', -1)]).limit(25))
        top_book_ids = [book['id'] for book in top_books]
        return jsonify({'top_books_by_clicks': top_book_ids})
    
    # Find the most clicked category by the user
    category_clicks = {}
    for interaction in user_interactions:
        book = books_collection.find_one({'id': int(interaction['book_id'])})
        if book:
            category = book.get('Category', 'Unknown')
            category_clicks[category] = category_clicks.get(category, 0) + interaction['clicks']
    
    most_clicked_category = max(category_clicks, key=category_clicks.get)
    # Get recommendations by age, gender, and category
    recommended_books = get_recommendations_by_age_gender_category(user_age, user_gender, most_clicked_category, limit=25)
    recommended_book_ids = [book['id'] for book in recommended_books]
    
    # Fill in the rest with top clicks if needed
    if len(recommended_book_ids) < 25:
        additional_books = list(books_collection.find({'id': {'$nin': recommended_book_ids}}, {'_id': 0, 'id': 1}).sort([('clicks', -1)]).limit(25 - len(recommended_book_ids)))
        recommended_book_ids.extend([book['id'] for book in additional_books])
    
    return jsonify({'top_books_by_clicks': recommended_book_ids})

@app.route('/stalls/<int:book_id>', methods=['GET'])
def stalls_by_book(book_id):
    # Find stalls related to the given book_id
    stalls = list(stalls_collection.find({'bookID': book_id}, {'_id': 0, 'stall_id': 1, 'IsAuthor': 1, 'stall_impressions': 1}))

    # Sort stalls by isAuthor (True first) and then by stall_impressions (descending)
    sorted_stalls = sorted(stalls, key=lambda x: (not x['IsAuthor'], -x['stall_impressions']))

    # Prepare JSON response with stall_id and rec flag (1 for isAuthor, 0 otherwise)
    response = [{'stall_id': stall['stall_id'], 'rec': 1 if stall['IsAuthor'] else 0} for stall in sorted_stalls]

    return jsonify({'stalls': response})

#@app.route('/top_clicks', methods=['GET'])
#def top_clicks():
#    top_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'clicks': 1}).sort([('clicks', -1)]).limit(5))
#    top_book_ids = [book['id'] for book in top_books]
#    return jsonify({'top_books_by_clicks': top_book_ids})

@app.route('/top_impressions', methods=['GET'])
def top_impressions():
    top_books = list(books_collection.find({}, {'_id': 0, 'id': 1, 'impressions': 1}).sort([('impressions', -1)]).limit(5))
    top_book_ids = [book['id'] for book in top_books]
    return jsonify({'top_books_by_impressions': top_book_ids})

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
