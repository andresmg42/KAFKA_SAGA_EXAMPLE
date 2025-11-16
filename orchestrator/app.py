"""
ORCHESTRATOR - Coordinates the Saga
Pure coordination logic - no business logic
"""
from flask import Flask, request, jsonify
from kafka import KafkaProducer, KafkaConsumer
import json
import os
import threading
import uuid

app = Flask(__name__)

KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

# Track saga states
sagas = {}

# Kafka producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

print("=" * 60)
print("ORCHESTRATOR - Saga Coordinator")
print("=" * 60)

# Saga workflow: 2 steps
WORKFLOW = [
    {
        'step': 1,
        'service': 'service-a',
        'action': 'deduct',
        'topic': 'service-a-deduct',
        'compensate_topic': 'service-a-refund'
    },
    {
        'step': 2,
        'service': 'service-b',
        'action': 'add',
        'topic': 'service-b-add',
        'compensate_topic': 'service-b-remove'
    }
]

def execute_step(saga_id, step_index):
    """Execute a saga step"""
    if saga_id not in sagas:
        return
    
    saga = sagas[saga_id]
    
    # Check if saga completed
    if step_index >= len(WORKFLOW):
        saga['status'] = 'COMPLETED'
        print(f"\n{'='*60}")
        print(f"✅ SAGA COMPLETED: {saga_id}")
        print(f"   Amount: ${saga['amount']}")
        print(f"   All steps successful!")
        print(f"{'='*60}\n")
        return
    
    # Get step details
    step = WORKFLOW[step_index]
    saga['current_step'] = step_index
    
    # Send command to service
    message = {
        'saga_id': saga_id,
        'amount': saga['amount']
    }
    
    print(f"\n⏩ STEP {step['step']}/2: {step['service']}.{step['action']}")
    print(f"   Sending command to {step['service']}...")
    
    producer.send(step['topic'], value=message)
    producer.flush()

def compensate_saga(saga_id, failed_step):
    """Rollback the saga (undo previous steps)"""
    if saga_id not in sagas:
        return
    
    saga = sagas[saga_id]
    saga['status'] = 'COMPENSATING'
    
    print(f"\n{'='*60}")
    print(f"⚠️  SAGA FAILED: {saga_id}")
    print(f"   Failed at step {failed_step + 1}")
    print(f"   Starting ROLLBACK...")
    print(f"{'='*60}")
    
    # Compensate all previous steps in reverse order
    for i in range(failed_step - 1, -1, -1):
        step = WORKFLOW[i]
        
        message = {
            'saga_id': saga_id,
            'amount': saga['amount']
        }
        
        print(f"\n🔄 COMPENSATING STEP {step['step']}: {step['service']}")
        producer.send(step['compensate_topic'], value=message)
        producer.flush()
    
    saga['status'] = 'ROLLED_BACK'
    print(f"\n{'='*60}")
    print(f"❌ SAGA ROLLED BACK: {saga_id}")
    print(f"   All changes reverted")
    print(f"{'='*60}\n")

def listen_for_responses():
    """Listen for responses from services"""
    consumer = KafkaConsumer(
        'orchestrator-response',
        bootstrap_servers=KAFKA_SERVERS,
        group_id='orchestrator-group',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest'
    )
    
    print("📡 Orchestrator listening for responses...")
    
    for message in consumer:
        data = message.value
        saga_id = data.get('saga_id')
        service = data.get('service')
        step_name = data.get('step')
        status = data.get('status')
        error = data.get('error')
        
        if saga_id not in sagas:
            continue
        
        saga = sagas[saga_id]
        current_step = saga['current_step']
        
        if status == 'SUCCESS':
            # Step succeeded, move to next step
            print(f"✅ Step {current_step + 1} SUCCESS from {service}")
            saga['completed_steps'].append(current_step)
            execute_step(saga_id, current_step + 1)
            
        elif status == 'FAILED':
            # Step failed, start compensation
            print(f"❌ Step {current_step + 1} FAILED from {service}")
            print(f"   Error: {error}")
            compensate_saga(saga_id, current_step)

# Start response listener
threading.Thread(target=listen_for_responses, daemon=True).start()

@app.route('/transfer', methods=['POST'])
def start_transfer():
    """Start a money transfer saga"""
    data = request.get_json()
    amount = data.get('amount', 0)
    
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    # Create saga
    saga_id = str(uuid.uuid4())[:8]
    
    sagas[saga_id] = {
        'saga_id': saga_id,
        'amount': amount,
        'status': 'STARTED',
        'current_step': 0,
        'completed_steps': []
    }
    
    print(f"\n{'='*60}")
    print(f"🚀 STARTING SAGA: {saga_id}")
    print(f"   Transfer: ${amount}")
    print(f"   From: Account A (Service A)")
    print(f"   To: Account B (Service B)")
    print(f"   Steps: 2")
    print(f"{'='*60}")
    
    # Start first step
    execute_step(saga_id, 0)
    
    return jsonify({
        'saga_id': saga_id,
        'amount': amount,
        'status': 'STARTED',
        'message': 'Transfer saga initiated'
    }), 202

@app.route('/saga/<saga_id>', methods=['GET'])
def get_saga(saga_id):
    """Get saga status"""
    if saga_id not in sagas:
        return jsonify({'error': 'Saga not found'}), 404
    
    return jsonify(sagas[saga_id])

@app.route('/sagas', methods=['GET'])
def list_sagas():
    """List all sagas"""
    return jsonify({
        'sagas': list(sagas.values()),
        'total': len(sagas),
        'completed': sum(1 for s in sagas.values() if s['status'] == 'COMPLETED'),
        'rolled_back': sum(1 for s in sagas.values() if s['status'] == 'ROLLED_BACK')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)