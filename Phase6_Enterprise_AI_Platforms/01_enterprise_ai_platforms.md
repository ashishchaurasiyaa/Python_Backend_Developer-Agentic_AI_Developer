# Enterprise AI Platforms — AWS Bedrock, Google Vertex AI, Azure OpenAI

## Quick Concepts
- **AWS Bedrock** = managed service for Claude + Titan + Llama via AWS — no model management
- **Google Vertex AI** = Gemini + PaLM + open models via GCP — integrated with Google Cloud
- **Azure OpenAI** = GPT-4 via Azure — data residency, compliance, enterprise SLAs
- **Why enterprises use these** = compliance, data privacy, VPC isolation, no data sent to third-party
- **IAM + VPC integration** = models run inside your cloud account — data never leaves

---

## Interview Questions & Answers

### Q1: AWS Bedrock — Claude aur other models kaise use karte hain?
**Answer:**
```python
# pip install boto3 anthropic[bedrock]

import boto3
import json

# ===== BOTO3 DIRECT — Claude on Bedrock =====
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1",
    # Auth: uses ~/.aws/credentials or IAM role
)

def claude_bedrock(prompt: str, model_id: str = "anthropic.claude-sonnet-4-6-20251001-v2:0") -> str:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    })
    
    response = bedrock.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json"
    )
    
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]

# Available models on Bedrock:
BEDROCK_MODELS = {
    "claude-sonnet": "anthropic.claude-sonnet-4-6-20251001-v2:0",
    "claude-haiku":  "anthropic.claude-haiku-4-5-20251001:0",
    "llama3-70b":    "meta.llama3-70b-instruct-v1:0",
    "titan-text":    "amazon.titan-text-express-v1",
    "mistral":       "mistral.mistral-7b-instruct-v0:2",
}

# ===== ANTHROPIC SDK — Bedrock integration =====
import anthropic

client = anthropic.AnthropicBedrock(
    aws_access_key="...",
    aws_secret_key="...",
    aws_region="us-east-1",
    # OR: uses boto3 credentials automatically
)

message = client.messages.create(
    model="anthropic.claude-sonnet-4-6-20251001-v2:0",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain RAG in simple terms"}]
)
print(message.content[0].text)

# ===== LITELLM — Bedrock abstraction =====
from litellm import completion

response = completion(
    model="bedrock/anthropic.claude-sonnet-4-6-20251001-v2:0",
    messages=[{"role": "user", "content": "Hello"}],
    aws_region_name="us-east-1",
)
print(response.choices[0].message.content)

# ===== STREAMING on Bedrock =====
def stream_claude_bedrock(prompt: str):
    response = bedrock.invoke_model_with_response_stream(
        modelId="anthropic.claude-sonnet-4-6-20251001-v2:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }),
        contentType="application/json",
        accept="application/json",
    )
    
    stream = response.get("body")
    for event in stream:
        chunk = json.loads(event["chunk"]["bytes"])
        if chunk.get("type") == "content_block_delta":
            yield chunk["delta"]["text"]
```

---

### Q2: Google Vertex AI — Gemini aur other models?
**Answer:**
```python
# pip install google-cloud-aiplatform vertexai

import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from vertexai.language_models import TextGenerationModel

# Initialize (uses Application Default Credentials)
vertexai.init(
    project="my-gcp-project",
    location="us-central1",
)

# ===== GEMINI on Vertex =====
model = GenerativeModel("gemini-1.5-pro")

response = model.generate_content(
    "Explain the difference between pgvector and Qdrant",
    generation_config=GenerationConfig(
        temperature=0.3,
        max_output_tokens=1024,
        top_p=0.9,
    ),
)
print(response.text)

# ===== MULTIMODAL with Vertex Gemini =====
import httpx, base64

def analyze_document(pdf_url: str, question: str) -> str:
    pdf_content = httpx.get(pdf_url).content
    pdf_part = Part.from_data(
        data=base64.standard_b64encode(pdf_content).decode(),
        mime_type="application/pdf"
    )
    
    model = GenerativeModel("gemini-1.5-pro")
    response = model.generate_content([pdf_part, question])
    return response.text

# ===== STREAMING with Vertex =====
def stream_gemini(prompt: str):
    model = GenerativeModel("gemini-1.5-pro")
    stream = model.generate_content(prompt, stream=True)
    for chunk in stream:
        yield chunk.text

# ===== LANGCHAIN with Vertex =====
from langchain_google_vertexai import ChatVertexAI

llm = ChatVertexAI(
    model_name="gemini-1.5-pro",
    project="my-gcp-project",
    location="us-central1",
    temperature=0.3,
)

response = llm.invoke("Explain LangGraph in simple terms")
print(response.content)

# ===== EMBEDDING with Vertex =====
from vertexai.language_models import TextEmbeddingModel

embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

def get_embeddings(texts: list[str]) -> list[list[float]]:
    embeddings = embedding_model.get_embeddings(texts)
    return [e.values for e in embeddings]
```

---

### Q3: Azure OpenAI — GPT-4 enterprise deployment?
**Answer:**
```python
# pip install openai  (Azure uses same SDK)

from openai import AzureOpenAI

# ===== AZURE OPENAI CLIENT =====
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    # e.g., https://mycompany.openai.azure.com/
)

def chat_azure(prompt: str, deployment_name: str = "gpt-4o") -> str:
    """
    Azure OpenAI uses 'deployment names' not model names.
    You deploy a model and give it a name in Azure portal.
    """
    response = client.chat.completions.create(
        model=deployment_name,    # Your deployment name, not "gpt-4o"
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.3,
    )
    return response.choices[0].message.content

# ===== EMBEDDINGS on Azure =====
def embed_azure(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model="text-embedding-ada-002",  # Your embedding deployment name
        input=texts,
    )
    return [item.embedding for item in response.data]

# ===== LANGCHAIN with Azure =====
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

llm = AzureChatOpenAI(
    azure_deployment="gpt-4o",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    temperature=0.3,
)

embeddings = AzureOpenAIEmbeddings(
    azure_deployment="text-embedding-ada-002",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

# ===== LITELLM — Azure abstraction =====
from litellm import completion

response = completion(
    model="azure/gpt-4o",       # prefix: azure/
    messages=[{"role": "user", "content": "Hello"}],
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
)
```

---

### Q4: Why enterprises use managed platforms over direct APIs?
**Answer:**
```
ENTERPRISE REQUIREMENTS:

1. DATA PRIVACY & COMPLIANCE:
   - Direct API: data sent to Anthropic/OpenAI servers
   - Bedrock/Vertex/Azure: data stays WITHIN your cloud account
   - GDPR, HIPAA, SOC2 — easier to comply with managed platforms
   - Healthcare, finance, government MUST use managed platforms

2. NETWORK ISOLATION (VPC):
   - Data never traverses public internet
   - VPC endpoint → Bedrock — private network path
   - Zero public IP exposure

3. IAM INTEGRATION:
   - Existing AWS/GCP/Azure IAM roles work directly
   - No separate API key management
   - Audit logs in CloudTrail/Cloud Audit Logs
   - Fine-grained permissions per service/user

4. ENTERPRISE SLAs:
   - Direct API: 99.9% uptime promise
   - Azure OpenAI: 99.9% SLA + Microsoft support contract
   - Bedrock: AWS Enterprise Support available
   - Dedicated throughput (provisioned concurrency)

5. COST AT SCALE:
   - Enterprise discount agreements with AWS/GCP/Azure
   - Consolidate billing (one invoice)
   - Reserved capacity pricing

6. EXISTING INFRASTRUCTURE:
   - Company already on AWS → add Bedrock, no new vendor
   - SSO, logging, monitoring — already in place
```

---

### Q5: IAM + VPC integration for secure AI?
**Answer:**
```python
# ===== AWS IAM POLICY for Bedrock =====
BEDROCK_IAM_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            "Resource": [
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-*",
                "arn:aws:bedrock:us-east-1::foundation-model/meta.llama3-*",
            ]
        }
    ]
}
# Attach this to EC2 instance role or Lambda execution role
# No API keys needed — boto3 uses instance metadata

# ===== VPC ENDPOINT for Bedrock =====
# Terraform:
VPC_ENDPOINT_TF = """
resource "aws_vpc_endpoint" "bedrock" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.us-east-1.bedrock-runtime"
  vpc_endpoint_type = "Interface"
  subnet_ids        = [aws_subnet.private.id]
  security_group_ids = [aws_security_group.bedrock.id]
  
  private_dns_enabled = true  # Use private DNS
}
# After this: boto3 calls go through private network, not internet
"""

# ===== EC2 with IAM ROLE (no credentials needed) =====
import boto3

# On EC2 with IAM role attached — no credentials needed!
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
# boto3 auto-fetches temporary credentials from instance metadata

# ===== COST COMPARISON =====
COST_COMPARISON = {
    "anthropic_direct": {
        "claude_sonnet_input": "$3.00/1M tokens",
        "claude_sonnet_output": "$15.00/1M tokens",
        "data_residency": "Anthropic servers",
        "compliance": "Self-managed"
    },
    "aws_bedrock": {
        "claude_sonnet_input": "$3.00/1M tokens",   # Same price
        "claude_sonnet_output": "$15.00/1M tokens",
        "data_residency": "Your AWS account",
        "compliance": "AWS compliance (HIPAA, SOC2, etc.)",
        "extras": "No extra charge for managed service"
    },
    "azure_openai": {
        "gpt4o_input": "$5.00/1M tokens",
        "gpt4o_output": "$15.00/1M tokens",
        "data_residency": "Your Azure subscription",
        "compliance": "Microsoft compliance framework",
        "extras": "Enterprise SLA, dedicated deployments"
    }
}
# Key insight: Bedrock doesn't add markup to model prices
# You pay same as direct API but get AWS-managed benefits
```

---

### Q6: LiteLLM — one interface for all enterprise platforms?
**Answer:**
```python
# pip install litellm

from litellm import completion, acompletion
import os

# ===== UNIFIED INTERFACE =====
# Same code, different providers

# Anthropic Direct
r1 = completion(model="claude-sonnet-4-6", messages=[{"role": "user", "content": "Hi"}])

# AWS Bedrock
r2 = completion(
    model="bedrock/anthropic.claude-sonnet-4-6-20251001-v2:0",
    messages=[{"role": "user", "content": "Hi"}],
)

# Azure OpenAI
r3 = completion(
    model="azure/gpt-4o",
    messages=[{"role": "user", "content": "Hi"}],
    api_base=os.getenv("AZURE_ENDPOINT"),
    api_version="2024-02-01",
)

# Google Vertex
r4 = completion(
    model="vertex_ai/gemini-1.5-pro",
    messages=[{"role": "user", "content": "Hi"}],
    vertex_project="my-project",
    vertex_location="us-central1",
)

# ===== FALLBACK CHAIN =====
from litellm import Router

router = Router(
    model_list=[
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "anthropic/claude-sonnet-4-6",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            }
        },
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "bedrock/anthropic.claude-sonnet-4-6-20251001-v2:0",
            }
        },
        {
            "model_name": "claude-fallback",
            "litellm_params": {
                "model": "azure/gpt-4o",
                "api_base": os.getenv("AZURE_ENDPOINT"),
                "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
                "api_version": "2024-02-01",
            }
        }
    ],
    fallbacks=[{"claude-fallback": ["claude-fallback"]}],
    # Auto-retry with next provider on failure
)

response = await router.acompletion(
    model="claude-fallback",
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

## Platform Selection Guide

```
USE DIRECT API (Anthropic/OpenAI/Google) WHEN:
  - Startup / early stage
  - No strict data compliance requirements
  - Want simplest setup
  - Cost-sensitive (same price, but simpler billing)

USE AWS BEDROCK WHEN:
  - Already on AWS infrastructure
  - Need HIPAA, SOC2 compliance
  - Want VPC isolation
  - Want to use IAM roles (no API key management)
  - Need Claude + Llama + other models from one place

USE AZURE OPENAI WHEN:
  - Enterprise Microsoft ecosystem (Office 365, Azure AD)
  - Need dedicated throughput (GPT-4 reserved capacity)
  - EU data residency required
  - Need Microsoft enterprise support contract

USE GOOGLE VERTEX AI WHEN:
  - Already on GCP
  - Need Gemini multimodal (vision, long context)
  - Want tight BigQuery / Cloud Storage integration
  - Research/academic (Google credits)

SENIOR INTERVIEW ANSWER:
  "I'd evaluate based on: (1) existing cloud vendor to minimize ops complexity,
   (2) compliance requirements — HIPAA/GDPR/SOC2 often mandate managed platforms,
   (3) model selection needs — Bedrock has most variety,
   (4) at startup, direct APIs are simpler; enterprise → Bedrock or Azure."
```
