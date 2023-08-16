from flask import Flask, request, jsonify
from decouple import config
import requests, random
from pymongo import MongoClient
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)



client = MongoClient(config('uri'))
db = client['hergele-api']
collection = db['hergele']
auth_log = db['log']

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

def authenticate_and_log_request():
    headers = request.headers
    auth_code = headers.get("X-Auth-Code")
    user_no = headers.get("X-User-No")
    filo = headers.get("X-Filo")
    user_document = collection.find_one({"userNo": user_no})
    
    if user_document and user_document.get("authCode") == auth_code and filo == 'hergele':
        return True
    
    else:
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        auth_attempt = {
            "timestamp": current_datetime,
            "request_headers": dict(headers),           
        }
        auth_log.insert_one(auth_attempt) # geri donen talepler farkli bir collection'a kaydediliyor.
        return False

@app.before_request
def before_request():
    if not authenticate_and_log_request():
        return jsonify({"message": "Authentication failed"}), 401

@app.route('/')
def index():
    return jsonify({"message": "OK: Authorized"}), 200

@app.post('/api/cards/add')
def add_card():
 
    _json = request.json
    _json["userNo"] = request.headers.get("X-User-No")  # tekrar ayni user 
    _json["authCode"] = request.headers.get("X-Auth-Code") # ve authcode giriliyor dolayisiyla baska user'a kart giremez.
    collection.insert_one(_json)

    return jsonify({'message': 'Card added successfully'}), 200

@app.post('/api/cards/')
def get_user_cards():

    user_no = request.headers.get("X-User-No") # header'dan user no aliniyor

    cards = list(collection.find({"userNo": user_no})) # userno'ya ait tum kartlar listeleniyor
    for card in cards: # birden fazla varsa hepsi listeleniyor.
        card["_id"] = str(card["_id"])

    if cards:
        return jsonify(cards), 200
    else:
        return jsonify({"message": "No cards found"}), 404

@app.post('/api/cards/payment/<cardno>')
def payment(cardno):
    user_no = request.headers.get("X-User-No") # user no'yu headerdan aliyoruz.
    payment = request.json.get("payment") # payment ile client talep yapiyor

    if user_no and cardno and payment is not None:
        selected_card = {"userNo": user_no, "selectedCard": cardno} # cardno ve userno eslesen spesifik kart
        card = collection.find_one(selected_card) 
        if card:
            current_balance = card.get("balance")
            new_balance = current_balance - payment # karttan odeme cek
            if new_balance >= 0:
                card['balance'] = new_balance
                card['last_payment_amount'] = payment
                collection.update_one(selected_card, {"$set": card}) # hersey ok ise kaydet.
                return jsonify({"message": "Balance updated successfully"}), 200
            else:
                return jsonify({"message": "Insufficient balance"}), 400
        else:
            return jsonify({"message": "Card not found"}), 404
    else:
        return jsonify({"message": "Invalid data"}), 400

@app.post('/api/cards/refund/<cardno>')
def refund(cardno):
    user_no = request.headers.get("X-User-No") # user no'yu headerdan aliyoruz.
   
    if user_no and cardno:
        selected_card = {"userNo": user_no, "selectedCard": cardno} # cardno ve userno eslesen spesifik kart
        card = collection.find_one(selected_card) 
        if card:
            last_payment_amount = card.get("last_payment_amount") # son cekilen parayi bul
            if last_payment_amount is not None:
                collection.update_one(selected_card, {"$inc": {"balance": last_payment_amount}, "$unset": {"last_payment_amount": None}}) # once cekilen parayi karta geri gonder daha sonra son cekilan para alanini sil
                return jsonify({"message": "Refund successful"}), 200
            else:
                return jsonify({"message": "No previous withdrawal to refund"}), 400
        else:
            return jsonify({"message": "Card not found"}), 404
    else:
        return jsonify({"message": "Invalid data"}), 400

@app.route('/populate')
def populate_database():    

    url = 'https://randomuser.me/api/?results=10'
    response = requests.get(url)
    data = response.json()
    cards = ["card1", "card2", "card3", "card4", "card5"]
    users = []
    userno = 0
    for random_user in data['results']:
        userno += 1 
        user = {
        "userNo": str(userno), 
        "authCode": str(random.randrange(111111, 999999, 6)), 
        "name": random_user['name']['first'],
        "surname": random_user['name']['last'],
        "birthDate": random_user['dob']['date'][:10],
        "phoneNumber": random_user['phone'],
        "email": random_user['email'],
        "selectedCard": random.choice(cards),
        "allCards": cards,
        "balance": random.randint(500, 5000)
    }
        users.append(user)
        
    collection.insert_many(users)
    collection.create_index("userNo", "selectedCard")

    return "Database is populated!"

if __name__ == '__main__':
    app.run(debug=True)









