#!/usr/bin/env python3
"""
Model Comparison Test - Compare how different models respond to the same question
Tests all models from models_list.json with the same prompt and question.

Models starting with "ai/" use Docker Model Runner at 192.168.50.66:12434
Other models use OpenAI API
"""

import asyncio
import httpx
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.test
load_dotenv('.env.test')

# Configuration from environment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DOCKER_MODEL_RUNNER_URL = os.getenv('DOCKER_MODEL_RUNNER_URL')
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Test question
TEST_QUESTION = "what's your favorite place you've ever sailed and why"

class ModelComparisonTest:
    def __init__(self):
        self.timeout = 60.0
        self.system_prompt = self.load_prompt()
        self.models = self.load_models()
        
        # Validate required environment variables
        if not OPENAI_API_KEY:
            print("❌ Error: OPENAI_API_KEY not found in .env.test")
        if not DOCKER_MODEL_RUNNER_URL:
            print("❌ Error: DOCKER_MODEL_RUNNER_URL not found in .env.test")
        
    def load_prompt(self):
        """Load system prompt from prompt.txt"""
        try:
            with open("prompt.txt", "r") as f:
                return f.read().strip()
        except Exception as e:
            print(f"❌ Error loading prompt.txt: {e}")
            return "You are a helpful assistant."
    
    def load_models(self):
        """Load models list from models_list.json"""
        try:
            with open("models_list.json", "r") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"❌ Error loading models_list.json: {e}")
            return {"dmr": [], "openai": []}
    
    async def test_docker_model(self, model_name):
        """Test models that start with 'ai' using Docker Model Runner"""
        print(f"🔧 Testing {model_name} via Docker Model Runner...")
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": TEST_QUESTION}
            ]
        }
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(DOCKER_MODEL_RUNNER_URL, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                response_time = time.time() - start_time
                response_text = data["choices"][0]["message"]["content"]
                
                print(f"✅ {model_name}: {response_time:.3f}s")
                print(f"📝 Response: {response_text[:100]}...")
                print()
                
                return {
                    "model": model_name,
                    "endpoint": "Docker Model Runner",
                    "response_time": response_time,
                    "success": True,
                    "response_text": response_text
                }
                
        except Exception as e:
            print(f"❌ {model_name} failed: {e}")
            print()
            return {
                "model": model_name,
                "endpoint": "Docker Model Runner",
                "response_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    async def test_openai_model(self, model_name):
        """Test OpenAI models using OpenAI API"""
        print(f"🌐 Testing {model_name} via OpenAI API...")
        
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": TEST_QUESTION}
            ]
        }
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OPENAI_API_URL, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                response_time = time.time() - start_time
                response_text = data["choices"][0]["message"]["content"]
                
                print(f"✅ {model_name}: {response_time:.3f}s")
                print(f"📝 Response: {response_text[:100]}...")
                print()
                
                return {
                    "model": model_name,
                    "endpoint": "OpenAI API",
                    "response_time": response_time,
                    "success": True,
                    "response_text": response_text
                }
                
        except Exception as e:
            print(f"❌ {model_name} failed: {e}")
            print()
            return {
                "model": model_name,
                "endpoint": "OpenAI API", 
                "response_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    async def run_comparison(self):
        """Run comparison test on all models"""
        print("🏴‍☠️ Mr. Bones Model Comparison Test")
        print("=" * 60)
        print(f"Test question: '{TEST_QUESTION}'")
        print(f"System prompt loaded from: prompt.txt")
        total_models = len(self.models.get("dmr", [])) + len(self.models.get("openai", []))
        print(f"Models to test: {total_models} (DMR: {len(self.models.get('dmr', []))}, OpenAI: {len(self.models.get('openai', []))})")
        print("=" * 60)
        print()
        
        results = []
        
        # Test DMR models
        for model in self.models.get("dmr", []):
            result = await self.test_docker_model(model)
            results.append(result)
        
        # Test OpenAI models
        for model in self.models.get("openai", []):
            result = await self.test_openai_model(model)
            results.append(result)
        
        # Generate summary
        self.print_summary(results)
        
        return results
    
    def print_summary(self, results):
        """Print detailed comparison summary"""
        print("\n" + "=" * 60)
        print("📊 MODEL COMPARISON SUMMARY")
        print("=" * 60)
        
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]
        
        print(f"✅ Successful: {len(successful_results)}/{len(results)}")
        print(f"❌ Failed: {len(failed_results)}/{len(results)}")
        print()
        
        if successful_results:
            print("🚀 RESPONSE TIMES:")
            successful_results.sort(key=lambda x: x["response_time"])
            for result in successful_results:
                print(f"  {result['model']:25} {result['response_time']:6.3f}s ({result['endpoint']})")
            print()
        
        if failed_results:
            print("❌ FAILED MODELS:")
            for result in failed_results:
                print(f"  {result['model']:25} - {result['error']}")
            print()
        
        print("📝 FULL RESPONSES:")
        print("=" * 60)
        for i, result in enumerate(successful_results, 1):
            print(f"{i}. {result['model']} ({result['endpoint']}):")
            print(f"   Time: {result['response_time']:.3f}s")
            print(f"   Response: {result['response_text']}")
            print("-" * 40)

async def main():
    """Run the model comparison test"""
    test = ModelComparisonTest()
    await test.run_comparison()

if __name__ == "__main__":
    asyncio.run(main())