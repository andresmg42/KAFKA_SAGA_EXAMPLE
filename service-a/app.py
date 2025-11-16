"""
SERVICE A - Manages Account A (Business Logic Only)
Receives commands from orchestrator via Kafka
"""
from flask import Flask, jsonify
from kafka import KafkaProducer, KafkaConsumer
import json
import os
import threading
import random

app = Flask(__name__)

KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

# Account A balance
account_balance = 1000.0

# Kafka producer (to send responses back to orchestrator)
producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

print("=" * 60)
print("SERVICE A - Account A")
print(f"Initial Balance: ${account_balance}")
print("=" * 60)

def deduct_money(saga_id, amount):
    """Deduct money from Account A"""
    global account_balance
    
    print(f"\n📨 RECEIVED: Deduct ${amount}")
    
    # Check if we have enough money
    if amount > account_balance:
        print(f"❌ FAILED: Insufficient funds")
        print(f"   Requested: ${amount}, Available: ${account_balance}")
        return False, "Insufficient funds"
    
    # Simulate random failure (20% chance)
    if random.random() < 0.2:
        print(f"❌ FAILED: System error")
        return False, "System error"
    
    # Deduct money
    old_balance = account_balance
    account_balance -= amount
    print(f"✅ SUCCESS: Deducted ${amount}")
    print(f"   Balance: ${old_balance} → ${account_balance}")
    
    return True, None

def refund_money(saga_id, amount):
    """Refund money to Account A (compensation)"""
    global account_balance
    
    print(f"\n🔄 COMPENSATION: Refund ${amount}")
    
    old_balance = account_balance
    account_balance += amount
    print(f"✅ Refunded ${amount}")
    print(f"   Balance: ${old_balance} → ${account_balance}")

def listen_to_orchestrator():
    """Listen for commands from orchestrator"""
    consumer = KafkaConsumer(
        'service-a-deduct',
        'service-a-refund',
        bootstrap_servers=KAFKA_SERVERS,
        group_id='service-a-group',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest'
    )
    
    print("📡 Service A listening for commands...")
    
    for message in consumer:
        data = message.value
        saga_id = data.get('saga_id')
        amount = data.get('amount')
        topic = message.topic
        
        if topic == 'service-a-deduct':
            # Execute deduct
            success, error = deduct_money(saga_id, amount)
            
            # Send response to orchestrator
            response = {
                'saga_id': saga_id,
                'service': 'service-a',
                'step': 'deduct',
                'status': 'SUCCESS' if success else 'FAILED',
                'error': error
            }
            producer.send('orchestrator-response', value=response)
            producer.flush()
            
        elif topic == 'service-a-refund':
            # Execute compensation
            refund_money(saga_id, amount)

# Start listener
threading.Thread(target=listen_to_orchestrator, daemon=True).start()

@app.route('/balance', methods=['GET'])
def get_balance():
    return jsonify({
        'account': 'Account A',
        'balance': account_balance
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)