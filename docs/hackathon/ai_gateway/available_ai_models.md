# WEX AI Gateway - Available Models

This document lists all available AI models in the WEX AI Gateway, organized by provider and optimized for different use cases.

## Azure OpenAI

### **azure-gpt-4o**
OpenAI's latest GPT-4o model, offering enhanced reasoning, speed, and efficiency compared to previous GPT-4 models.
- **Best for**: Complex analysis, strategic reasoning, sophisticated text generation
- **Use cases**: Business intelligence, complex problem solving, detailed analysis

### **azure-gpt-4o-mini**
A smaller, optimized version of GPT-4o, designed for lower latency and cost-efficiency.
- **Best for**: Fast classification, simple tasks, high-volume processing
- **Use cases**: Query classification, data extraction, simple analysis

### **azure-textembedding-ada-002**
A powerful text embedding model based on OpenAI's Ada series.
- **Best for**: Semantic search, clustering, recommendation systems
- **Use cases**: Vector search, content similarity, document retrieval

### **azure-text-embedding-3-large**
An enhanced embedding model from OpenAI designed for more efficient and accurate semantic representation.
- **Best for**: High-accuracy semantic search, complex document analysis
- **Use cases**: Advanced RAG systems, precise content matching

### **azure-text-embedding-3-small**
A smaller version of OpenAI's embedding-3 model that prioritizes latency and storage efficiency.
- **Best for**: Fast embedding generation, cost-effective vector search
- **Use cases**: Real-time search, large-scale embedding generation

## Azure AI Foundry

### **azure-r1** ✨
DeepSeek-R1 excels at reasoning tasks using a step-by-step training process.
- **Best for**: Scientific reasoning, coding tasks, complex logic problems
- **Use cases**: Code analysis, mathematical reasoning, step-by-step problem solving
- **⚠️ Compliance Note**: Not suitable for US-only data residency requirements

### **azure-v3-0324** ✨
DeepSeek-V3-0324 is an advanced Mixture-of-Experts (MoE) language model.
- **Best for**: Multi-domain expertise, efficient large-scale processing
- **Use cases**: Complex multi-faceted analysis, expert-level reasoning
- **⚠️ Compliance Note**: Not suitable for US-only data residency requirements

## Bedrock Anthropic

### **bedrock-claude-3-opus-v1**
Claude 3 Opus offers exceptional performance on highly complex tasks, can process images and return text outputs.
- **Best for**: Highly complex reasoning, multimodal tasks, premium analysis
- **Use cases**: Advanced problem solving, image analysis, complex reasoning

### **bedrock-claude-opus-4-v1** 🏆
Claude Opus 4 is Anthropic's most intelligent model and is state-of-the-art for coding and agent capabilities.
- **Best for**: Coding, agentic search, most complex reasoning tasks
- **Use cases**: Advanced coding assistance, complex agent workflows, sophisticated analysis

### **bedrock-claude-sonnet-4-v1** 🏆
Claude Sonnet 4 balances performance with speed and cost-efficiency, ideal for tasks like code generation and real-time decision support.
- **Best for**: Balanced performance, code generation, real-time analysis
- **Use cases**: Business intelligence, code reviews, strategic decision support

### **bedrock-claude-3-7-sonnet-v1**
Claude 3.7 Sonnet offers extended thinking—the ability to solve complex problems with careful, step-by-step reasoning.
- **Best for**: Step-by-step reasoning, complex problem solving
- **Use cases**: Strategic analysis, complex text generation, detailed reasoning

### **bedrock-claude-3-5-haiku-v1**
A newer Claude 3 Haiku model offering the lowest latency for simple text generation tasks.
- **Best for**: Fast response, simple tasks, high-volume processing
- **Use cases**: Quick classification, simple text generation, real-time responses

### **bedrock-claude-3-5-sonnet-v2**
An upgraded version of Claude 3.5 Sonnet, good for coding tasks and agentic capabilities.
- **Best for**: Coding tasks, agent workflows, balanced performance
- **Use cases**: Code analysis, automated workflows, general text generation

### **bedrock-claude-3-5-sonnet-v1**
The original version of Claude 3.5 Sonnet, balances performance and efficiency.
- **Best for**: General text generation, balanced performance
- **Use cases**: Content generation, analysis, general AI tasks

### **bedrock-claude-3-haiku-v1**
A fast and compact multimodal Claude 3 model, optimized for responsiveness and cost-effectiveness.
- **Best for**: Fast multimodal processing, cost-effective operations
- **Use cases**: Quick image analysis, high-volume text processing

## Bedrock Mistral

### **bedrock-mistral-7b-instruct-v0**
A 7-billion-parameter open-weight model from Mistral AI, optimized for instruction-following tasks.
- **Best for**: Instruction following, cost-effective processing
- **Use cases**: Simple task execution, basic text generation

### **bedrock-mistral-small-2402-v1**
A smaller version of Mistral AI's model, optimized for cost efficiency and straightforward tasks.
- **Best for**: Cost efficiency, simple tasks
- **Use cases**: Basic text processing, simple analysis

### **bedrock-mistral-large-2402-v1**
A larger, more capable version of Mistral AI's model, optimized for better reasoning and generation.
- **Best for**: Advanced reasoning, complex text generation
- **Use cases**: Detailed analysis, sophisticated text generation

### **bedrock-mixtral-8x7b-instruct-v0**
Mixtral, a mixture-of-experts model (8x7B), enabling highly efficient and accurate text generation.
- **Best for**: Efficient processing, expert-level responses
- **Use cases**: Multi-domain analysis, efficient text generation

### **bedrock-pixtral-large-2502-v1**
Pixtral Large, a 124B open-weights multimodal model with enhanced image understanding.
- **Best for**: Advanced image understanding, multimodal analysis
- **Use cases**: Image analysis, visual content processing

## Bedrock Amazon

### **bedrock-titan-embed-image-v1**
Amazon's Titan model for generating image embeddings, useful for similarity search and classification.
- **Best for**: Image embeddings, visual similarity search
- **Use cases**: Image classification, visual content retrieval

### **bedrock-titan-embed-text-v1**
A text embedding model optimized for semantic search, retrieval-augmented generation (RAG), and NLP tasks.
- **Best for**: Text embeddings, RAG systems
- **Use cases**: Semantic search, document retrieval, content matching

### **bedrock-titan-embed-text-v2**
A newer version of Titan's text embedding model with multilingual support and flexible embedding sizes.
- **Best for**: Multilingual embeddings, flexible vector sizes
- **Use cases**: Cross-language search, international content processing

### **bedrock-titan-text-premier-v1**
A higher-performance advanced text model designed for superior performance across enterprise applications.
- **Best for**: Enterprise applications, high-performance text generation
- **Use cases**: Business content generation, enterprise AI applications

### **bedrock-titan-text-express-v1**
A high-performance text model focused on speed and expressiveness.
- **Best for**: Fast text generation, chatbots
- **Use cases**: Real-time chat, quick content generation

### **bedrock-titan-text-lite-v1**
A lighter, cost-efficient version optimized for simple NLP tasks.
- **Best for**: Cost efficiency, simple NLP tasks
- **Use cases**: Basic text processing, simple analysis

### **bedrock-nova-pro-v1**
A highly capable multimodal model great for multilingual reasoning over text, images, and videos.
- **Best for**: Multimodal reasoning, sophisticated applications
- **Use cases**: Multi-step reasoning, RAG, agentic workflows

### **bedrock-nova-lite-v1**
A cost-effective and efficient variant of the Nova Pro multimodal model.
- **Best for**: Cost-effective multimodal processing
- **Use cases**: Basic multimodal tasks, efficient processing

### **bedrock-nova-micro-v1**
A low-latency text-only model for cost-effective text-based tasks.
- **Best for**: Fast text processing, cost efficiency
- **Use cases**: Language understanding, translation, code completion

### **bedrock-nova-canvas-v1**
An image generation model that can take text prompts and images as input.
- **Best for**: Image generation, visual content creation
- **Use cases**: Creative content, visual design, image synthesis

### **bedrock-nova-premier-v1**
The most capable and advanced multimodal model for sophisticated multi-agent workflows.
- **Best for**: Advanced multimodal workflows, deep contextual understanding
- **Use cases**: Complex agent systems, sophisticated analysis, multi-tool integration

## Bedrock Meta

### **bedrock-llama3-8b-instruct-v1**
An 8-billion-parameter version, optimized for balanced performance and efficiency.
- **Best for**: Balanced performance, efficient processing
- **Use cases**: General text generation, instruction following

### **bedrock-llama3-70b-instruct-v1**
A 70-billion-parameter model, optimized for large-scale AI applications.
- **Best for**: Complex reasoning, large-scale applications
- **Use cases**: Advanced analysis, sophisticated text generation

### **bedrock-llama3-1-8b-instruct-v1**
Smaller Llama 3.1 variant with expanded 128K context length and improved reasoning capabilities.
- **Best for**: Long context processing, improved reasoning
- **Use cases**: Document analysis, extended conversations

### **bedrock-llama3-1-70b-instruct-v1**
Larger Llama 3.1 variant that offers improved reasoning and multilingual capabilities.
- **Best for**: Advanced reasoning, multilingual tasks
- **Use cases**: Complex analysis, international applications

### **bedrock-llama3-2-1b-instruct-v1**
The smallest LLaMA 3 variant, optimized for low-cost and fast inference.
- **Best for**: Cost efficiency, fast processing
- **Use cases**: Simple tasks, high-volume processing

### **bedrock-llama3-2-3b-instruct-v1**
A 3-billion-parameter model, lightweight and cost-efficient for general NLP tasks.
- **Best for**: Lightweight processing, cost efficiency
- **Use cases**: Basic NLP, simple text generation

### **bedrock-llama3-2-11b-instruct-v1**
An 11-billion-parameter version optimized for instruction-following tasks.
- **Best for**: Instruction following, balanced performance
- **Use cases**: Task execution, general AI applications

### **bedrock-llama3-2-90b-instruct-v1**
A 90-billion-parameter version, designed for complex generative tasks and deep understanding.
- **Best for**: Complex tasks, deep understanding
- **Use cases**: Advanced analysis, sophisticated reasoning

### **bedrock-llama3-3-70b-instruct-v1**
Known for improved reasoning, understanding of nuances and context, and multilingual translation.
- **Best for**: Nuanced understanding, multilingual tasks
- **Use cases**: Translation, contextual analysis, international applications

### **bedrock-llama4-scout-17b-instruct-v1**
Great for complex natural language tasks, like answering questions, writing, summarization, or coding help.
- **Best for**: Complex NLP tasks, coding assistance
- **Use cases**: Question answering, writing assistance, code help

### **bedrock-llama4-maverick-17b-instruct-v1**
May excel in tasks needing creativity, brainstorming, or in-depth explanation with nuanced understanding.
- **Best for**: Creative tasks, brainstorming, nuanced explanations
- **Use cases**: Creative writing, ideation, detailed explanations

## Bedrock DeepSeek

### **bedrock-r1-v1** ✨
Use this for searching through large document corpora or answering questions by retrieving relevant info.
- **Best for**: Document search, information retrieval
- **Use cases**: Large corpus search, question answering, document analysis

## Bedrock Cohere

### **bedrock-command-r-plus-v1**
A highly capable generative text model optimized for complex RAG, tool use, and advanced conversational tasks.
- **Best for**: Complex RAG, tool use, advanced conversations
- **Use cases**: Sophisticated RAG systems, tool integration, complex dialogues

### **bedrock-command-r-v1**
A strong generative model balanced for conversational AI, RAG, and general text generation.
- **Best for**: Conversational AI, balanced RAG
- **Use cases**: Chatbots, general RAG, text generation

### **bedrock-embed-english-v3**
A powerful embedding model designed for creating vector representations of English text.
- **Best for**: English text embeddings, semantic search
- **Use cases**: English content search, clustering, similarity

### **bedrock-embed-multilingual-v3**
An embedding model for generating vector representations across multiple languages.
- **Best for**: Multilingual embeddings, cross-lingual search
- **Use cases**: International content, cross-language search

### **bedrock-command-text-v14**
Command Text, a generative text model focused on producing well-written text.
- **Best for**: Well-written text, copywriting
- **Use cases**: Content creation, summarization, copywriting

### **bedrock-command-light-text-v14**
A faster, lighter version of Command Text, suitable for less complex tasks where speed is a priority.
- **Best for**: Fast text generation, simple tasks
- **Use cases**: Quick content, simple text processing

## Bedrock Stability AI

### **bedrock-stable-diffusion-xl-v1**
SDXL generates images of high quality in virtually any art style with vibrant colors and better contrast.
- **Best for**: High-quality image generation, artistic content
- **Use cases**: Creative visuals, art generation, design content

## Bedrock AI21 Labs

### **bedrock-jamba-1-5-mini-v1** ✨
A small version of the Jamba 1.5 family. Excels at text generation and specialized functions.
- **Best for**: Text generation, specialized functions
- **Use cases**: Question answering, summarization, information extraction, classification

### **bedrock-jamba-1-5-large-v1** ✨
A performant model with 256K token effective context window, excellent for complex tasks.
- **Best for**: Complex tasks, large context processing
- **Use cases**: Long document analysis, complex text generation, large-scale processing

---

## 🎯 Model Selection Recommendations

### **For Strategic Business Intelligence Platform:**

#### **🏆 Primary Model: `bedrock-claude-sonnet-4-v1`**
- **Perfect for**: Strategic business intelligence, real-time decision support
- **Why**: Balances performance with speed and cost-efficiency
- **Use cases**: Complex cross-table analysis, strategic insights, executive recommendations
- **Same model family as this conversation** - proven effectiveness!

#### **🚀 Secondary Model: `azure-gpt-4o-mini`**
- **Perfect for**: Fast classification, pre-analysis, simple tasks
- **Why**: Cost-effective for high-volume processing
- **Use cases**: Query classification, table group selection, data extraction

#### **🔍 Embedding Model: `azure-text-embedding-3-small`**
- **Perfect for**: Vector generation across all 24 tables
- **Why**: Optimal balance of performance and cost for large-scale embeddings
- **Use cases**: Semantic search, content similarity, document retrieval

#### **💎 Premium Alternative: `bedrock-claude-opus-4-v1`**
- **Perfect for**: Most complex analysis requiring maximum intelligence
- **Why**: Anthropic's most intelligent model, state-of-the-art capabilities
- **Use cases**: When cost is less important than maximum analytical capability

### **Model Usage Strategy:**
1. **Pre-Analysis**: `azure-gpt-4o-mini` for fast query classification
2. **Semantic Search**: `azure-text-embedding-3-small` for vector generation
3. **Strategic Analysis**: `bedrock-claude-sonnet-4-v1` for business intelligence
4. **Premium Analysis**: `bedrock-claude-opus-4-v1` for most complex scenarios

### **Cost Optimization:**
- Use **Claude Sonnet 4** for 80% of complex analysis (balanced cost/performance)
- Use **GPT-4o-mini** for 90% of simple tasks (cost-effective)
- Reserve **Claude Opus 4** for 5% of most critical analysis (premium capability)

This strategy provides optimal performance while managing costs effectively for the 3-day hackathon implementation.
