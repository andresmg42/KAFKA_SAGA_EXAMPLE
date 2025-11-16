"""
SERVICE B - Manages Account B (Business Logic Only)
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

# Account B balance
account_balance = 500.0

# Kafka producer (to send responses back to orchestrator)
producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

print("=" * 60)
print("SERVICE B - Account B")
print(f"Initial Balance: ${account_balance}")
print("=" * 60)

def add_money(saga_id, amount):
    """Add money to Account B"""
    global account_balance
    
    print(f"\n📨 RECEIVED: Add ${amount}")
    
    # Simulate random failure (30% chance)
    if random.random() < 0.3:
        print(f"❌ FAILED: Account verification failed")
        return False, "Account verification failed"
    
    # Add money
    old_balance = account_balance
    account_balance += amount
    print(f"✅ SUCCESS: Added ${amount}")
    print(f"   Balance: ${old_balance} → ${account_balance}")
    
    return True, None

def remove_money(saga_id, amount):
    """Remove money from Account B (compensation)"""
    global account_balance
    
    print(f"\n🔄 COMPENSATION: Remove ${amount}")
    
    old_balance = account_balance
    account_balance -= amount
    print(f"✅ Removed ${amount}")
    print(f"   Balance: ${old_balance} → ${account_balance}")

def listen_to_orchestrator():
    """Listen for commands from orchestrator"""
    consumer = KafkaConsumer(
        'service-b-add',
        'service-b-remove',
        bootstrap_servers=KAFKA_SERVERS,
        group_id='service-b-group',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest'
    )
    
    print("📡 Service B listening for commands...")
    
    for message in consumer:
        data = message.value
        saga_id = data.get('saga_id')
        amount = data.get('amount')
        topic = message.topic
        
        if topic == 'service-b-add':
            # Execute add
            success, error = add_money(saga_id, amount)
            
            # Send response to orchestrator
            response = {
                'saga_id': saga_id,
                'service': 'service-b',
                'step': 'add',
                'status': 'SUCCESS' if success else 'FAILED',
                'error': error
            }
            producer.send('orchestrator-response', value=response)
            producer.flush()
            
        elif topic == 'service-b-remove':
            # Execute compensation
            remove_money(saga_id, amount)

# Start listener
threading.Thread(target=listen_to_orchestrator, daemon=True).start()

@app.route('/balance', methods=['GET'])
def get_balance():
    return jsonify({
        'account': 'Account B',
        'balance': account_balance
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)