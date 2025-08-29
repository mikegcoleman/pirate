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

# Test questions will be loaded from JSON file

def apply_format_post_processing(content):
    """Apply fast format post-processing for Mr. Bones character consistency"""
    import re
    
    original_content = content
    
    # Fix UTF-8 encoding issues (mojibake)
    content = content.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Replace contractions with expanded forms
    contractions_map = {
        "don't": "do not", "Don't": "Do not", "DON'T": "DO NOT",
        "can't": "cannot", "Can't": "Cannot", "CAN'T": "CANNOT", 
        "won't": "will not", "Won't": "Will not", "WON'T": "WILL NOT",
        "I'm": "I am", "I'M": "I AM",
        "you're": "you are", "You're": "You are", "YOU'RE": "YOU ARE",
        "we're": "we are", "We're": "We are", "WE'RE": "WE ARE",
        "they're": "they are", "They're": "They are", "THEY'RE": "THEY ARE",
        "it's": "it is", "It's": "It is", "IT'S": "IT IS",
        "that's": "that is", "That's": "That is", "THAT'S": "THAT IS",
        "what's": "what is", "What's": "What is", "WHAT'S": "WHAT IS",
        "here's": "here is", "Here's": "Here is", "HERE'S": "HERE IS",
        "there's": "there is", "There's": "There is", "THERE'S": "THERE IS",
        "let's": "let us", "Let's": "Let us", "LET'S": "LET US",
        "I'll": "I will", "I'LL": "I WILL",
        "you'll": "you will", "You'll": "You will", "YOU'LL": "YOU WILL",
        "he'll": "he will", "He'll": "He will", "HE'LL": "HE WILL",
        "she'll": "she will", "She'll": "She will", "SHE'LL": "SHE WILL",
        "we'll": "we will", "We'll": "We will", "WE'LL": "WE WILL",
        "they'll": "they will", "They'll": "They will", "THEY'LL": "THEY WILL",
        "I've": "I have", "I'VE": "I HAVE",
        "you've": "you have", "You've": "You have", "YOU'VE": "YOU HAVE",
        "we've": "we have", "We've": "We have", "WE'VE": "WE HAVE",
        "they've": "they have", "They've": "They have", "THEY'VE": "THEY HAVE",
        "I'd": "I would", "I'D": "I WOULD",
        "you'd": "you would", "You'd": "You would", "YOU'D": "YOU WOULD",
        "he'd": "he would", "He'd": "He would", "HE'D": "HE WOULD",
        "she'd": "she would", "She'd": "She would", "SHE'D": "SHE WOULD",
        "we'd": "we would", "We'd": "We would", "WE'D": "WE WOULD",
        "they'd": "they would", "They'd": "They would", "THEY'D": "THEY WOULD"
    }
    
    # Apply contraction replacements
    for contraction, expansion in contractions_map.items():
        content = re.sub(r'\b' + re.escape(contraction) + r'\b', expansion, content)
    
    # Replace Mr. with Mister
    content = re.sub(r'\bMr\.', 'Mister', content)
    content = re.sub(r'\bmr\.', 'mister', content)  # Handle lowercase
    
    # Fix common UTF-8 issues
    utf8_fixes = {
        'â€™': "'",  # Right single quotation mark
        'â€œ': '"',  # Left double quotation mark  
        'â€': '"',   # Right double quotation mark
        'â€¦': '...',  # Ellipsis
        'â€"': '-',   # Em dash
        'â€"': '--',  # En dash
    }
    
    for broken, fixed in utf8_fixes.items():
        content = content.replace(broken, fixed)
    
    return content

class ModelComparisonTest:
    def __init__(self):
        self.timeout = 60.0
        self.system_prompt = self.load_prompt()
        self.models = self.load_models()
        self.test_questions = self.load_test_questions()
        
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
    
    def load_test_questions(self):
        """Load test questions from model_comparison_test_questions.json"""
        try:
            with open("../model_comparison_test_questions.json", "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading model_comparison_test_questions.json: {e}")
            return []
    
    async def test_docker_model(self, model_name, question):
        """Test models that start with 'ai' using Docker Model Runner"""
        print(f"🔧 Testing {model_name} via Docker Model Runner...")
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question}
            ]
        }
        
        # Add optimal decode parameters for Mistral models
        if 'mistral' in model_name.lower():
            payload.update({
                'temperature': 0.6,
                'top_p': 0.9,
                'max_tokens': 120,
                'presence_penalty': 0.3,
                'frequency_penalty': 0.2
            })
            print(f"🎯 Applied Mistral optimization parameters for {model_name}")
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(DOCKER_MODEL_RUNNER_URL, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                response_time = time.time() - start_time
                response_text = data["choices"][0]["message"]["content"]
                
                # Apply format post-processing
                processed_response = apply_format_post_processing(response_text)
                
                print(f"✅ {model_name}: {response_time:.3f}s")
                print(f"📝 Response: {processed_response[:100]}...")
                print()
                
                return {
                    "model": model_name,
                    "endpoint": "Docker Model Runner",
                    "response_time": response_time,
                    "success": True,
                    "response_text": processed_response
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
    
    async def test_openai_model(self, model_name, question):
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
                {"role": "user", "content": question}
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
                
                # Apply format post-processing
                processed_response = apply_format_post_processing(response_text)
                
                print(f"✅ {model_name}: {response_time:.3f}s")
                print(f"📝 Response: {processed_response[:100]}...")
                print()
                
                return {
                    "model": model_name,
                    "endpoint": "OpenAI API",
                    "response_time": response_time,
                    "success": True,
                    "response_text": processed_response
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
        """Run comparison test on all models with all personas and questions"""
        print("🏴‍☠️ Mr. Bones Model Comparison Test")
        print("=" * 60)
        print(f"System prompt loaded from: prompt.txt")
        total_models = len(self.models.get("dmr", [])) + len(self.models.get("openai", []))
        total_questions = sum(len(persona["questions"]) for persona in self.test_questions)
        print(f"Models to test: {total_models} (DMR: {len(self.models.get('dmr', []))}, OpenAI: {len(self.models.get('openai', []))})")
        print(f"Personas: {len(self.test_questions)}")
        print(f"Total questions per model: {total_questions}")
        print(f"Total test combinations: {total_models * total_questions}")
        print("=" * 60)
        print()
        
        all_results = []
        
        # Iterate through each persona
        for persona_idx, persona_data in enumerate(self.test_questions, 1):
            persona_name = persona_data["persona"]
            questions = persona_data["questions"]
            
            print(f"🎭 PERSONA {persona_idx}/5: {persona_name}")
            print("=" * 60)
            
            # Iterate through each question for this persona
            for question_idx, question in enumerate(questions, 1):
                print(f"\n📝 Question {question_idx}/10: {question}")
                print("-" * 40)
                
                question_results = []
                
                # Test all DMR models with this question
                for model in self.models.get("dmr", []):
                    result = await self.test_docker_model(model, question)
                    result["persona"] = persona_name
                    result["persona_idx"] = persona_idx
                    result["question"] = question
                    result["question_idx"] = question_idx
                    question_results.append(result)
                    all_results.append(result)
                
                # Test all OpenAI models with this question
                for model in self.models.get("openai", []):
                    result = await self.test_openai_model(model, question)
                    result["persona"] = persona_name
                    result["persona_idx"] = persona_idx
                    result["question"] = question
                    result["question_idx"] = question_idx
                    question_results.append(result)
                    all_results.append(result)
                
                # Quick summary for this question
                successful = [r for r in question_results if r["success"]]
                failed = [r for r in question_results if not r["success"]]
                print(f"  ✅ Successful: {len(successful)}/{len(question_results)}")
                if failed:
                    print(f"  ❌ Failed: {len(failed)} models")
        
        # Generate final summary
        self.print_comprehensive_summary(all_results)
        
        return all_results
    
    def print_comprehensive_summary(self, results):
        """Print comprehensive summary of all test results"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE MODEL COMPARISON SUMMARY")
        print("=" * 80)
        
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]
        
        print(f"✅ Total Successful: {len(successful_results)}/{len(results)}")
        print(f"❌ Total Failed: {len(failed_results)}/{len(results)}")
        print()
        
        # Model Performance Overview
        if successful_results:
            print("🚀 MODEL PERFORMANCE OVERVIEW:")
            model_stats = {}
            for result in successful_results:
                model = result["model"]
                if model not in model_stats:
                    model_stats[model] = {"times": [], "count": 0, "endpoint": result["endpoint"]}
                model_stats[model]["times"].append(result["response_time"])
                model_stats[model]["count"] += 1
            
            # Calculate averages and sort by performance
            for model, stats in model_stats.items():
                stats["avg_time"] = sum(stats["times"]) / len(stats["times"])
                stats["min_time"] = min(stats["times"])
                stats["max_time"] = max(stats["times"])
            
            sorted_models = sorted(model_stats.items(), key=lambda x: x[1]["avg_time"])
            
            for model, stats in sorted_models:
                print(f"  {model:30} Avg: {stats['avg_time']:6.3f}s | Min: {stats['min_time']:6.3f}s | Max: {stats['max_time']:6.3f}s | Tests: {stats['count']:2d} ({stats['endpoint']})")
            print()
        
        # Failure Analysis
        if failed_results:
            print("❌ FAILURE ANALYSIS:")
            failure_stats = {}
            for result in failed_results:
                model = result["model"]
                error = result.get("error", "Unknown error")
                if model not in failure_stats:
                    failure_stats[model] = {"errors": [], "count": 0}
                failure_stats[model]["errors"].append(error)
                failure_stats[model]["count"] += 1
            
            for model, stats in failure_stats.items():
                print(f"  {model:30} Failed: {stats['count']} times")
                # Show unique error types
                unique_errors = list(set(stats["errors"]))
                for error in unique_errors[:3]:  # Limit to first 3 unique errors
                    print(f"    └─ {error}")
            print()
        
        # Persona Analysis
        print("🎭 PERSONA ANALYSIS:")
        persona_stats = {}
        for result in successful_results:
            persona = result["persona"]
            if persona not in persona_stats:
                persona_stats[persona] = {"times": [], "count": 0}
            persona_stats[persona]["times"].append(result["response_time"])
            persona_stats[persona]["count"] += 1
        
        for persona, stats in persona_stats.items():
            if stats["count"] > 0:
                avg_time = sum(stats["times"]) / len(stats["times"])
                print(f"  {persona:45} Avg: {avg_time:6.3f}s | Tests: {stats['count']:2d}")
        print()
        
        # Cold Start Analysis - Model Performance by Question Order
        print("🔥 COLD START ANALYSIS:")
        print("   (Response times by question order to detect model warm-up patterns)")
        print("-" * 80)
        
        # Group results by model and persona, then analyze question order
        model_persona_analysis = {}
        for result in successful_results:
            model = result["model"]
            persona = result["persona"]
            question_idx = result["question_idx"]
            
            key = f"{model}|{persona}"
            if key not in model_persona_analysis:
                model_persona_analysis[key] = {}
            
            model_persona_analysis[key][question_idx] = result["response_time"]
        
        # Print analysis for each model-persona combination
        for key, question_times in model_persona_analysis.items():
            model, persona = key.split("|", 1)
            if len(question_times) >= 5:  # Only analyze if we have enough data points
                sorted_questions = sorted(question_times.items())
                times = [time for _, time in sorted_questions]
                
                # Calculate trends
                first_half_avg = sum(times[:len(times)//2]) / (len(times)//2)
                second_half_avg = sum(times[len(times)//2:]) / (len(times) - len(times)//2)
                improvement = first_half_avg - second_half_avg
                improvement_pct = (improvement / first_half_avg * 100) if first_half_avg > 0 else 0
                
                print(f"📊 {model[:25]:25} | {persona[:30]:30}")
                print(f"   Question Times: {' '.join([f'{t:.2f}s' for t in times])}")
                print(f"   First Half Avg: {first_half_avg:.3f}s | Second Half Avg: {second_half_avg:.3f}s")
                
                if improvement > 0.1:  # Significant improvement threshold
                    print(f"   🚀 WARM-UP DETECTED: {improvement:.3f}s faster ({improvement_pct:+.1f}%)")
                elif improvement < -0.1:  # Getting slower
                    print(f"   🐌 SLOWDOWN DETECTED: {abs(improvement):.3f}s slower ({improvement_pct:+.1f}%)")
                else:
                    print(f"   ⚖️  STABLE: {improvement:+.3f}s difference ({improvement_pct:+.1f}%)")
                print()
        print()
        
        # Full responses organized by persona and question for model evaluation
        print("📝 FULL RESPONSES BY PERSONA AND QUESTION:")
        print("=" * 80)
        
        # Group results by persona and question for easy comparison
        persona_question_responses = {}
        for result in successful_results:
            persona = result["persona"]
            question_idx = result["question_idx"]
            question = result["question"]
            
            if persona not in persona_question_responses:
                persona_question_responses[persona] = {}
            if question_idx not in persona_question_responses[persona]:
                persona_question_responses[persona][question_idx] = {
                    "question": question,
                    "responses": []
                }
            
            persona_question_responses[persona][question_idx]["responses"].append(result)
        
        # Print organized results
        for persona_idx in range(1, 6):  # Personas 1-5
            persona_data = None
            for persona, questions in persona_question_responses.items():
                # Find the persona by checking if any result has the right persona_idx
                if questions and any(r["persona_idx"] == persona_idx for q in questions.values() for r in q["responses"]):
                    persona_data = (persona, questions)
                    break
            
            if persona_data:
                persona, questions = persona_data
                print(f"\n🎭 PERSONA {persona_idx}/5: {persona}")
                print("=" * 60)
                
                for question_idx in sorted(questions.keys()):
                    question_data = questions[question_idx]
                    print(f"\n📝 Question {question_idx}/10: {question_data['question']}")
                    print("-" * 40)
                    
                    # Sort responses by model name for consistent ordering
                    sorted_responses = sorted(question_data["responses"], key=lambda x: x["model"])
                    
                    for response in sorted_responses:
                        print(f"🤖 {response['model']} ({response['response_time']:.3f}s, {response['endpoint']}):")
                        print(f"   {response['response_text']}")
                        print()
        
        print("=" * 80)

async def main():
    """Run the model comparison test"""
    test = ModelComparisonTest()
    await test.run_comparison()

if __name__ == "__main__":
    asyncio.run(main())