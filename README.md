# Simple Saga with Orchestrator - Money Transfer

The **simplest example** to understand Saga pattern with orchestrator and Kafka.

## 🎯 Architecture

```
┌─────────────────────────────────┐
│      ORCHESTRATOR (Port 8000)   │
│    Coordinates the workflow     │
└─────────────────────────────────┘
            │
    ┌───────┴───────┐
    ↓               ↓
┌─────────┐     ┌─────────┐
│SERVICE A│     │SERVICE B│
│(Port    │     │(Port    │
│ 8001)   │     │ 8002)   │
│         │     │         │
│Account A│     │Account B│
│$1000    │     │$500     │
└─────────┘     └─────────┘
```

## 🔄 How It Works

### Success Flow:
```
1. YOU: Send request to Orchestrator
   POST /transfer {"amount": 100}
   
2. ORCHESTRATOR: "Start saga, execute step 1"
   → Sends to Kafka topic: service-a-deduct
   
3. SERVICE A: "Deduct $100"
   Account A: $1000 → $900
   → Sends response to Kafka: orchestrator-response (SUCCESS)
   
4. ORCHESTRATOR: "Step 1 succeeded, execute step 2"
   → Sends to Kafka topic: service-b-add
   
5. SERVICE B: "Add $100"
   Account B: $500 → $600
   → Sends response to Kafka: orchestrator-response (SUCCESS)
   
6. ORCHESTRATOR: "All steps done!"
   ✅ SAGA COMPLETED
```

### Failure Flow:
```
1. YOU: Send request to Orchestrator
   
2. ORCHESTRATOR: Execute step 1
   → service-a-deduct
   
3. SERVICE A: Deduct $100 ✅
   Account A: $1000 → $900
   → orchestrator-response (SUCCESS)
   
4. ORCHESTRATOR: Execute step 2
   → service-b-add
   
5. SERVICE B: FAILED! ❌
   → orchestrator-response (FAILED)
   
6. ORCHESTRATOR: "Step 2 failed, start rollback!"
   → service-a-refund (compensation)
   
7. SERVICE A: Refund $100
   Account A: $900 → $1000
   
8. ORCHESTRATOR: "Rollback complete"
   ❌ SAGA ROLLED BACK
```

## 📁 Project Structure

```
simple-saga/
├── docker-compose.yml
├── orchestrator/
│   ├── Dockerfile
│   └── app.py
├── service-a/
│   ├── Dockerfile
│   └── app.py
└── service-b/
    ├── Dockerfile
    └── app.py
```

## 🚀 Setup

### 1. Create folders
```bash
mkdir -p simple-saga/{orchestrator,service-a,service-b}
cd simple-saga
```

### 2. Create files

Copy the artifacts:
- `docker-compose.yml` → root
- `orchestrator/app.py` → orchestrator code
- `service-a/app.py` → service-a code
- `service-b/app.py` → service-b code
- `Dockerfile` → copy to orchestrator, service-a, and service-b (same file)

### 3. Start
```bash
docker-compose up -d --build

# Wait 10 seconds
sleep 10
```

## 🧪 Testing

### Test 1: Successful Transfer

```bash
curl -X POST http://localhost:8000/transfer \
  -H "Content-Type: application/json" \
  -d '{"amount": 100}'
```

**Response:**
```json
{
  "saga_id": "abc123",
  "amount": 100,
  "status": "STARTED",
  "message": "Transfer saga initiated"
}
```

**Watch orchestrator logs:**
```bash
docker-compose logs -f orchestrator
```

You'll see:
```
============================================================
🚀 STARTING SAGA: abc123
   Transfer: $100
   From: Account A (Service A)
   To: Account B (Service B)
   Steps: 2
============================================================

⏩ STEP 1/2: service-a.deduct
   Sending command to service-a...

✅ Step 1 SUCCESS from service-a

⏩ STEP 2/2: service-b.add
   Sending command to service-b...

✅ Step 2 SUCCESS from service-b

============================================================
✅ SAGA COMPLETED: abc123
   Amount: $100
   All steps successful!
============================================================
```

### Test 2: Watch Service Logs

**Service A:**
```bash
docker-compose logs -f service-a
```

You'll see:
```
📨 RECEIVED: Deduct $100
✅ SUCCESS: Deducted $100
   Balance: $1000 → $900
```

**Service B:**
```bash
docker-compose logs -f service-b
```

You'll see:
```
📨 RECEIVED: Add $100
✅ SUCCESS: Added $100
   Balance: $500 → $600
```

### Test 3: Check Balances

```bash
curl http://localhost:8001/balance  # Service A
curl http://localhost:8002/balance  # Service B
```

### Test 4: Multiple Transfers (See Failures)

Service B fails 30% of the time, Service A fails 20% of the time.

```bash
for i in {1..5}; do
  curl -X POST http://localhost:8000/transfer \
    -H "Content-Type: application/json" \
    -d '{"amount": 50}'
  echo ""
  sleep 1
done
```

**Watch orchestrator for failures:**
```bash
docker-compose logs -f orchestrator
```

When failure happens:
```
⏩ STEP 1/2: service-a.deduct
✅ Step 1 SUCCESS from service-a

⏩ STEP 2/2: service-b.add
❌ Step 2 FAILED from service-b
   Error: Account verification failed

============================================================
⚠️  SAGA FAILED: xyz789
   Failed at step 2
   Starting ROLLBACK...
============================================================

🔄 COMPENSATING STEP 1: service-a

============================================================
❌ SAGA ROLLED BACK: xyz789
   All changes reverted
============================================================
```

**Service A will show:**
```
🔄 COMPENSATION: Refund $50
✅ Refunded $50
   Balance: $900 → $950
```

### Test 5: View All Sagas

```bash
curl http://localhost:8000/sagas
```

## 🔑 Key Concepts

### 1. Orchestrator (Coordinator)
- **Knows the workflow**: Step 1 then Step 2
- **Sends commands** to services via Kafka
- **Handles responses** from services
- **Triggers rollback** if any step fails
- **No business logic** - pure coordination

### 2. Services (Workers)
- **Listen for commands** on Kafka topics
- **Execute business logic** (deduct/add money)
- **Send responses** back via Kafka
- **Execute compensation** when told to rollback
- **Don't know about saga** - just execute commands

### 3. Kafka Topics

**Command Topics** (orchestrator → services):
- `service-a-deduct` - Tell Service A to deduct money
- `service-a-refund` - Tell Service A to refund (compensation)
- `service-b-add` - Tell Service B to add money
- `service-b-remove` - Tell Service B to remove (compensation)

**Response Topic** (services → orchestrator):
- `orchestrator-response` - Services report SUCCESS or FAILED

## 📊 Message Flow Diagram

```
Orchestrator                Kafka                   Service A
     |                        |                         |
     |-- send --------------->|                         |
     |  (service-a-deduct)    |                         |
     |                        |-------- deliver ------->|
     |                        |                         |
     |                        |                    (execute)
     |                        |                         |
     |                        |<----- send response ----|
     |<--- deliver -----------|  (orchestrator-response)|
     |                        |                         |
  (decide next step)
     |
     |-- send --------------->|
     |  (service-b-add)       |-------- deliver ------->| Service B
     |                        |                         |
     |                        |                    (execute)
     |                        |                         |
     |                        |<----- send response ----|
     |<--- deliver -----------|                         |
     |                        |
  (saga complete)
```

## 💡 Code Walkthrough

### Orchestrator Key Parts:

```python
# Workflow definition
WORKFLOW = [
    {'step': 1, 'service': 'service-a', 'topic': 'service-a-deduct', ...},
    {'step': 2, 'service': 'service-b', 'topic': 'service-b-add', ...}
]

# Execute step
def execute_step(saga_id, step_index):
    step = WORKFLOW[step_index]
    producer.send(step['topic'], message)  # Send command via Kafka

# Handle response
if status == 'SUCCESS':
    execute_step(saga_id, current_step + 1)  # Next step
elif status == 'FAILED':
    compensate_saga(saga_id, current_step)   # Rollback
```

### Service A Key Parts:

```python
# Listen for commands
consumer = KafkaConsumer('service-a-deduct', 'service-a-refund')

# Execute command
if topic == 'service-a-deduct':
    account_balance -= amount
    send_response('SUCCESS' or 'FAILED')
    
elif topic == 'service-a-refund':
    account_balance += amount  # Compensation
```

## 🎓 Why This Pattern?

### Without Orchestrator (Bad):
```
Service A ←→ Service B
```
- Services talk directly
- Each service needs to know about others
- Hard to change workflow
- Messy coordination logic

### With Orchestrator (Good):
```
    Orchestrator
       ↙   ↘
Service A  Service B
```
- Services are independent
- Orchestrator knows the workflow
- Easy to add more services
- Clear separation of concerns

## 🛠️ Common Commands

```bash
# Watch all logs
docker-compose logs -f

# Watch specific service
docker-compose logs -f orchestrator
docker-compose logs -f service-a
docker-compose logs -f service-b

# Check balances
curl http://localhost:8001/balance
curl http://localhost:8002/balance

# Check saga status
curl http://localhost:8000/sagas

# Clean restart
docker-compose down -v
docker-compose up -d --build
```

## 🎯 What You Learned

1. **Orchestrator pattern**: Central coordinator manages workflow
2. **Kafka for communication**: Services don't talk directly
3. **Saga compensation**: Automatic rollback on failure
4. **Separation of concerns**: Orchestrator = coordination, Services = business logic
5. **Event-driven architecture**: Asynchronous, decoupled services

## 🚀 Next Steps

Now that you understand the basics:
- Add a 3rd service (Service C)
- Add more steps to the workflow
- Use a real database instead of in-memory
- Add retry logic
- Add timeouts

---

**This is the simplest saga with orchestrator example!** 🎉

The orchestrator coordinates everything while services just execute commands.
