#!/usr/bin/env python3
"""
VentureLens - AI-Powered Business Idea Analyzer

A concise multi-agent system that interviews users about their business ideas
and generates comprehensive PDF analysis reports using Praval's decorator API.

Agent Architecture:
- Interviewer: Asks sequential questions to understand the business
- Analyst: Evaluates viability across multiple business dimensions  
- Reporter: Generates polished PDF reports with analysis
- Coordinator: Manages workflow and user interaction

Usage:
    python venturelens.py
"""

import sys
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/Users/rajesh/Github/praval/src')

from praval import agent, chat, broadcast, start_agents

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Simple shared state for business analysis
venture = {
    "idea": "",
    "responses": {},
    "analysis": {},
    "market_research": {},
    "questions_asked": 0,
    "max_questions": 20,
    "stage": "starting",
    "interview_started": False
}

# ==========================================
# MULTI-AGENT BUSINESS ANALYSIS SYSTEM
# ==========================================

@agent("interviewer", channel="venture", responds_to=["start_interview", "answer_provided"])
def conduct_interview(spore):
    """Dynamically ask questions to understand the business idea."""
    message_type = spore.knowledge.get("type")
    
    if message_type == "start_interview" and not venture["interview_started"]:
        venture["idea"] = spore.knowledge.get("idea", "")
        venture["stage"] = "interviewing"
        venture["questions_asked"] = 0
        venture["interview_started"] = True
        
        print(f"\n🎯 Let's analyze your idea: '{venture['idea']}'")
        print("I'll ask you questions to understand your business better.\n")
        
        # Ask first question
        first_question = "What specific problem does your business idea solve?"
        print(f"📝 Question 1: {first_question}")
        venture["current_question"] = "problem"
        return {"type": "question_asked", "question_key": "problem"}
    
    elif message_type == "answer_provided":
        # Store the answer
        answer = spore.knowledge.get("answer", "")
        question_key = spore.knowledge.get("question_key", "")
        if not answer or question_key in venture["responses"]:
            return  # Skip if empty answer or already processed
            
        venture["responses"][question_key] = answer
        venture["questions_asked"] += 1
        
        logging.info(f"📝 Answer {venture['questions_asked']} received, generating next question...")
        
        # Let LLM decide what to ask next based on information gathered
        if venture["questions_asked"] < venture["max_questions"]:
            try:
                # Create context of what we know so far
                context = f"Business idea: {venture['idea']}\n"
                for key, resp in venture["responses"].items():
                    context += f"{key}: {resp}\n"
                
                next_question_prompt = f"""
                Based on this business idea information, what's the most important question to ask next?
                
                {context}
                
                Questions asked so far: {venture['questions_asked']}/{venture['max_questions']}
                
                If ALL these key areas are covered with sufficient detail, respond with "COMPLETE".
                Otherwise, ask about the most important missing area:
                - Solution details (specific features, how it works)
                - Target market (who exactly, market size, customer segments)
                - Competition (direct competitors, competitive advantages)
                - Revenue model (pricing, monetization strategy, revenue streams)  
                - Resources/feasibility (team, funding, timeline, technical requirements)
                - Market validation (customer research, demand evidence)
                - Risks and challenges (biggest obstacles, mitigation strategies)
                
                Respond with either "COMPLETE" or just the question text.
                """
                
                next_question = chat(next_question_prompt, timeout=8.0).strip()
                
                if next_question.upper() == "COMPLETE" or venture["questions_asked"] >= 8:
                    print("\n✅ Enough information gathered! Researching market data...")
                    venture["stage"] = "researching"
                    return {"type": "start_research"}
                else:
                    question_number = venture["questions_asked"] + 1
                    print(f"\n📝 Question {question_number}: {next_question}")
                    venture["current_question"] = f"question_{question_number}"
                    return {"type": "question_asked", "question_key": venture["current_question"]}
                    
            except Exception as e:
                # Fallback: complete interview if LLM fails
                logging.warning(f"Question generation failed: {e}")
                print("\n✅ Interview complete! Researching market data...")
                venture["stage"] = "researching"  
                return {"type": "start_research"}
        else:
            # Max questions reached
            print("\n✅ Maximum questions reached! Researching market data...")
            venture["stage"] = "researching"
            return {"type": "start_research"}

@agent("researcher", channel="venture", responds_to=["start_research"])
def conduct_market_research(spore):
    """Search for market data, competitors, and trends related to the business idea."""
    idea = venture["idea"]
    responses = venture["responses"]
    
    logging.info("🔍 Conducting market research and competitive analysis...")
    
    research_data = {}
    
    # 1. Search for competitors and market size
    try:
        competitor_query = f"{idea} competitors market analysis"
        market_info = search_web(competitor_query, max_results=5)
        research_data["market_analysis"] = market_info
        logging.info(f"✅ Found market analysis data ({len(market_info)} results)")
    except Exception as e:
        logging.warning(f"Market analysis search failed: {e}")
        research_data["market_analysis"] = []
    
    # 2. Search for industry trends and growth
    try:
        trends_query = f"{idea} industry trends growth 2024 2025"
        trends_info = search_web(trends_query, max_results=3)
        research_data["industry_trends"] = trends_info
        logging.info(f"✅ Found industry trends ({len(trends_info)} results)")
    except Exception as e:
        logging.warning(f"Trends search failed: {e}")
        research_data["industry_trends"] = []
    
    # 3. Search for funding and startup information
    try:
        funding_query = f"{idea} startup funding investment venture capital"
        funding_info = search_web(funding_query, max_results=3)
        research_data["funding_landscape"] = funding_info
        logging.info(f"✅ Found funding data ({len(funding_info)} results)")
    except Exception as e:
        logging.warning(f"Funding search failed: {e}")
        research_data["funding_landscape"] = []
    
    # 4. Analyze the search results with LLM
    try:
        research_summary = analyze_search_results(idea, responses, research_data)
        research_data["summary"] = research_summary
    except Exception as e:
        logging.warning(f"Research analysis failed: {e}")
        research_data["summary"] = "Research analysis unavailable"
    
    venture["market_research"] = research_data
    venture["stage"] = "analyzing"
    
    print("✅ Market research complete! Analyzing your business idea...")
    return {"type": "research_complete"}

@agent("analyst", channel="venture", responds_to=["research_complete"])
def analyze_business_viability(spore):
    """Analyze the business idea across multiple dimensions."""
    logging.info("🧠 Analyzing business viability...")
    
    idea = venture["idea"]
    responses = venture["responses"]
    
    # Extract all responses and market research for comprehensive analysis
    all_responses = "\n".join([f"{key}: {value}" for key, value in responses.items()])
    market_research = venture.get("market_research", {})
    research_summary = market_research.get("summary", "No market research available")
    
    # Create comprehensive analysis using LLM with market data
    analysis_prompt = f"""
    Analyze this business idea comprehensively using both interview data and market research:
    
    Business Idea: {idea}
    
    Interview Responses:
    {all_responses}
    
    Market Research Findings:
    {research_summary}
    
    Please provide comprehensive analysis in this EXACT JSON format:
    {{
        "viability_score": 7.5,
        "problem_solution_fit": 8.0,
        "market_potential": 7.0, 
        "competitive_advantage": 6.5,
        "revenue_potential": 7.5,
        "execution_feasibility": 6.0,
        "problem_description": "Detailed 2-3 paragraph analysis of the problem space, pain points, market gap, and problem validation evidence",
        "solution_description": "Comprehensive 2-3 paragraph description of the solution approach, key features, differentiation, and value proposition", 
        "target_market_analysis": "Detailed 2-3 paragraph analysis covering customer segments, market size (TAM/SAM/SOM), customer personas, buying behavior, and market validation evidence",
        "competition_analysis": "Comprehensive competitive landscape analysis covering direct competitors, indirect alternatives, competitive advantages, market positioning, and differentiation strategy",
        "revenue_model_assessment": "Detailed revenue model analysis including pricing strategy, revenue streams, unit economics, scalability, and financial projections framework",
        "resource_requirements": "Comprehensive resource analysis covering team composition, funding requirements by stage, technical infrastructure, operational needs, and timeline",
        "key_risks": "Detailed risk assessment covering market risks, technical risks, competitive risks, execution risks, and mitigation strategies for each",
        "go_to_market_strategy": "Detailed go-to-market plan including customer acquisition channels, marketing strategy, sales process, partnerships, and launch strategy",
        "financial_projections": "Revenue projections framework, cost structure analysis, break-even analysis, and key financial metrics",
        "technology_assessment": "Technical feasibility, development complexity, scalability considerations, and technology stack recommendations",
        "strengths": ["detailed strength with explanation", "another strength with context", "third strength with reasoning"],
        "weaknesses": ["detailed weakness with impact analysis", "another weakness with mitigation ideas", "third weakness"],
        "opportunities": ["specific market opportunity with sizing", "technology opportunity with timeline", "partnership opportunity"],
        "threats": ["competitive threat with likelihood", "market threat with impact", "regulatory/technical threat"],
        "recommendations": ["specific actionable recommendation with timeline", "another recommendation with resources needed", "third recommendation with success metrics"],
        "next_steps": ["immediate 30-day action item", "60-day milestone with deliverables", "90-day goal with success criteria"]
    }}
    
    Score each dimension 0-10. Be extremely thorough, specific, and provide actionable insights. Each description should be 2-3 detailed paragraphs minimum.
    """
    
    try:
        analysis_text = chat(analysis_prompt, timeout=20.0)  # Increased timeout
        
        # Try to parse as JSON with better error handling
        try:
            import json
            # Clean up the response - sometimes LLMs add extra text
            analysis_text_clean = analysis_text.strip()
            if analysis_text_clean.startswith("```json"):
                analysis_text_clean = analysis_text_clean.replace("```json", "").replace("```", "").strip()
            elif analysis_text_clean.startswith("```"):
                analysis_text_clean = analysis_text_clean.replace("```", "").strip()
            
            # Find JSON content if wrapped in text
            start_idx = analysis_text_clean.find("{")
            end_idx = analysis_text_clean.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_content = analysis_text_clean[start_idx:end_idx]
                analysis = json.loads(json_content)
            else:
                analysis = json.loads(analysis_text_clean)
                
        except Exception as json_error:
            logging.warning(f"JSON parsing failed: {json_error}")
            # Create comprehensive fallback analysis based on interview responses
            analysis = create_fallback_analysis(idea, responses, market_research)
        
        venture["analysis"] = analysis
        venture["stage"] = "analyzed"
        
        logging.info(f"✅ Analysis complete - Viability score: {analysis.get('viability_score', 'N/A')}")
        return {"type": "analysis_complete", "score": analysis.get("viability_score")}
        
    except Exception as e:
        logging.error(f"❌ Analysis failed: {e}")
        # Provide basic fallback analysis
        venture["analysis"] = {
            "viability_score": 5.0,
            "analysis_text": "Analysis could not be completed due to technical issues.",
            "error": str(e)
        }
        return {"type": "analysis_complete", "score": 5.0}

@agent("reporter", channel="venture", responds_to=["analysis_complete"])
def generate_pdf_report(spore):
    """Generate a comprehensive PDF business analysis report."""
    logging.info("📄 Generating PDF report...")
    
    try:
        # Create professional Markdown report
        markdown_content = create_markdown_report()
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"VentureLens_Analysis_{timestamp}"
        
        # Try Pandoc PDF first
        pdf_file = f"{base_filename}.pdf"
        try:
            import subprocess
            
            # Save temporary Markdown file
            temp_markdown = f"temp_{base_filename}.md"
            with open(temp_markdown, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Try Pandoc PDF generation
            pandoc_cmd = [
                'pandoc', temp_markdown, '-o', pdf_file,
                '--pdf-engine=xelatex', '--toc', '--number-sections',
                '--variable', 'geometry:margin=1in'
            ]
            
            result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Clean up temp file
                import os
                os.remove(temp_markdown)
                final_file = pdf_file
                logging.info(f"✅ Professional PDF generated: {final_file}")
            else:
                raise Exception("Pandoc failed")
                
        except Exception:
            # Fallback to HTML
            html_file = f"{base_filename}.html"
            html_content = markdown_to_html(markdown_content)
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            final_file = html_file
            logging.info(f"✅ HTML report generated: {final_file}")
        
        venture["report_file"] = final_file
        venture["stage"] = "complete"
        return {"type": "report_generated", "filename": final_file}
        
    except Exception as e:
        logging.error(f"❌ Report generation failed: {e}")
        return {"type": "report_error", "error": str(e)}

@agent("presenter", channel="venture", responds_to=["report_generated"], auto_broadcast=False)
def show_final_results(spore):
    """Display the final analysis results and auto-open reports in browser."""
    # Prevent multiple calls
    if venture.get("presentation_complete", False):
        return
    
    filename = spore.knowledge.get("filename", "")
    analysis = venture["analysis"]
    
    print("\n" + "="*60)
    print("🎯 VENTURELENS BUSINESS ANALYSIS COMPLETE")
    print("="*60)
    
    # Show key metrics
    score = analysis.get("viability_score", "N/A")
    print(f"\n📊 Overall Viability Score: {score}/10")
    
    if isinstance(analysis.get("strengths"), list) and analysis["strengths"]:
        print(f"\n💪 Key Strengths:")
        for strength in analysis["strengths"][:3]:
            print(f"   • {strength}")
    
    if isinstance(analysis.get("recommendations"), list) and analysis["recommendations"]:
        print(f"\n🎯 Top Recommendations:")
        for rec in analysis["recommendations"][:3]:
            print(f"   • {rec}")
    
    print(f"\n📄 Detailed Report: {filename}")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"💡 Business Idea: {venture['idea']}")
    
    # Auto-open reports in browser
    auto_open_reports(filename)
    
    print("\n" + "="*60)
    
    # Mark as complete to prevent duplicate calls
    venture["stage"] = "complete"
    venture["presentation_complete"] = True

# ==========================================
# MARKET RESEARCH FUNCTIONS
# ==========================================

def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Enhanced web search using multiple strategies and APIs."""
    
    # Strategy 1: Try SerpAPI (if available)
    serpapi_results = try_serpapi_search(query, max_results)
    if serpapi_results:
        return serpapi_results
    
    # Strategy 2: Try web scraping approach
    scraping_results = try_web_scraping_search(query, max_results)
    if scraping_results:
        return scraping_results
    
    # Strategy 3: Generate intelligent mock data using LLM
    logging.info(f"🤖 Generating market intelligence for: {query}")
    return generate_market_intelligence(query, max_results)

def try_serpapi_search(query: str, max_results: int) -> List[Dict]:
    """Try SerpAPI for Google search results (requires SERPAPI_KEY environment variable)."""
    try:
        import os
        serpapi_key = os.getenv("SERPAPI_KEY")
        if not serpapi_key:
            return None
        
        search_url = "https://serpapi.com/search"
        params = {
            "q": query,
            "engine": "google",
            "api_key": serpapi_key,
            "num": max_results
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for result in data.get("organic_results", [])[:max_results]:
            results.append({
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "url": result.get("link", ""),
                "source": "Google Search"
            })
        
        if results:
            logging.info(f"✅ SerpAPI search successful: {len(results)} results")
            return results
            
    except Exception as e:
        logging.warning(f"SerpAPI search failed: {e}")
        return None

def try_web_scraping_search(query: str, max_results: int) -> List[Dict]:
    """Try basic web scraping for search results."""
    try:
        # Use requests-html for JavaScript rendering (if available)
        try:
            from requests_html import HTMLSession
            session = HTMLSession()
        except ImportError:
            return None
        
        # Search DuckDuckGo HTML (doesn't block as aggressively)
        search_url = "https://duckduckgo.com/html/"
        params = {"q": query}
        
        response = session.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        
        # Parse results (simplified)
        results = []
        # Basic parsing would go here - omitted for brevity
        # This is a placeholder for demonstration
        
        return None  # Simplified - would return parsed results
        
    except Exception as e:
        logging.warning(f"Web scraping search failed: {e}")
        return None

def generate_market_intelligence(query: str, max_results: int) -> List[Dict]:
    """Generate intelligent market research data using LLM when search APIs fail."""
    try:
        # Use LLM to generate realistic market intelligence
        intelligence_prompt = f"""
        Generate realistic market research data for this business idea query: "{query}"
        
        Provide {max_results} research findings that include:
        1. Market size and growth data
        2. Key competitors and market players
        3. Industry trends and insights
        4. Investment/funding information
        5. Technology trends related to this space
        
        Format each finding as:
        Title: [Descriptive title]
        Summary: [2-3 sentence insight]
        Source: [Realistic source like "Market Research Report 2024" or "Industry Analysis"]
        
        Be specific with numbers, percentages, and company names where realistic.
        """
        
        llm_response = chat(intelligence_prompt, timeout=12.0)
        
        # Parse LLM response into structured data
        results = parse_llm_market_intelligence(llm_response, query)
        
        logging.info(f"🤖 Generated {len(results)} market intelligence insights")
        return results
        
    except Exception as e:
        logging.warning(f"LLM market intelligence generation failed: {e}")
        # Final fallback with structured placeholder data
        return generate_fallback_intelligence(query, max_results)

def parse_llm_market_intelligence(llm_response: str, query: str) -> List[Dict]:
    """Parse LLM response into structured market intelligence data."""
    results = []
    
    # Simple parsing - look for Title/Summary patterns
    sections = llm_response.split("\n\n")
    for section in sections[:5]:  # Max 5 insights
        lines = section.strip().split("\n")
        
        title = ""
        summary = ""
        source = "AI Market Intelligence"
        
        for line in lines:
            if line.startswith("Title:"):
                title = line.replace("Title:", "").strip()
            elif line.startswith("Summary:"):
                summary = line.replace("Summary:", "").strip()
            elif line.startswith("Source:"):
                source = line.replace("Source:", "").strip()
        
        if title and summary:
            results.append({
                "title": title,
                "snippet": summary,
                "url": f"https://example.com/research/{query.replace(' ', '-')}",
                "source": source
            })
    
    # If parsing failed, create from full response
    if not results:
        results.append({
            "title": f"Market Intelligence: {query}",
            "snippet": llm_response[:300] + "..." if len(llm_response) > 300 else llm_response,
            "url": "",
            "source": "AI-Generated Market Intelligence"
        })
    
    return results

def generate_fallback_intelligence(query: str, max_results: int) -> List[Dict]:
    """Generate structured fallback market intelligence when all other methods fail."""
    base_insights = [
        {
            "title": f"Market Size Analysis for {query}",
            "snippet": f"Market analysis indicates growing demand in the {query} sector with significant opportunities for new entrants and innovative solutions.",
            "url": f"https://www.example.com/market-analysis/{query.replace(' ', '-')}",
            "source": "Market Research Database"
        },
        {
            "title": f"Competitive Landscape in {query}",
            "snippet": f"The competitive landscape for {query} shows fragmentation with opportunities for differentiation through technology and customer experience.",
            "url": f"https://www.example.com/competitive-analysis/{query.replace(' ', '-')}",
            "source": "Industry Analysis Report"
        },
        {
            "title": f"Investment Trends in {query}",
            "snippet": f"Investment activity in the {query} space has shown steady growth with increased interest from both strategic and financial investors.",
            "url": f"https://www.example.com/funding-trends/{query.replace(' ', '-')}",
            "source": "Venture Capital Database"
        }
    ]
    
    return base_insights[:max_results]

def analyze_search_results(idea: str, responses: Dict, research_data: Dict) -> str:
    """Use LLM to analyze and summarize the market research findings."""
    try:
        # Compile all search results
        market_info = research_data.get("market_analysis", [])
        trends_info = research_data.get("industry_trends", [])
        funding_info = research_data.get("funding_landscape", [])
        
        search_context = ""
        
        if market_info:
            search_context += "MARKET ANALYSIS:\n"
            for result in market_info:
                search_context += f"- {result['title']}: {result['snippet'][:200]}...\n"
        
        if trends_info:
            search_context += "\nINDUSTRY TRENDS:\n"
            for result in trends_info:
                search_context += f"- {result['title']}: {result['snippet'][:200]}...\n"
        
        if funding_info:
            search_context += "\nFUNDING LANDSCAPE:\n"
            for result in funding_info:
                search_context += f"- {result['title']}: {result['snippet'][:200]}...\n"
        
        analysis_prompt = f"""
        Based on the market research below, provide insights about this business idea: "{idea}"
        
        {search_context}
        
        Provide a concise analysis covering:
        1. Market size and opportunity
        2. Key competitors identified
        3. Industry trends and growth potential
        4. Funding landscape and investor interest
        5. Market validation evidence
        
        Keep it under 500 words and focus on actionable insights.
        """
        
        return chat(analysis_prompt, timeout=12.0)
        
    except Exception as e:
        logging.warning(f"Research analysis failed: {e}")
        return "Market research analysis could not be completed due to technical limitations."

def create_fallback_analysis(idea: str, responses: Dict, market_research: Dict) -> Dict:
    """Create comprehensive fallback analysis when LLM analysis fails."""
    
    # Extract key information from responses
    problem = responses.get('problem', 'Problem not specified')
    solution = responses.get('Question 2', responses.get('solution', 'Solution not specified'))
    market = responses.get('Question 3', responses.get('target_market', 'Target market not specified'))
    differentiation = responses.get('Question 4', responses.get('competition', 'Differentiation not specified'))
    
    return {
        "viability_score": 6.5,
        "problem_solution_fit": 7.0,
        "market_potential": 6.5,
        "competitive_advantage": 7.5,
        "revenue_potential": 6.0,
        "execution_feasibility": 5.5,
        
        "problem_description": f"Problem Analysis: {problem}\n\nThis business idea addresses a legitimate need in the market. The problem space shows potential for a scalable solution, though market validation will be crucial for success.",
        
        "solution_description": f"Solution Approach: {solution}\n\nThe proposed solution demonstrates innovation potential. Key success factors will include execution quality, user experience design, and market fit validation.",
        
        "target_market_analysis": f"Target Market: {market}\n\nThe identified target market shows promise, though detailed market sizing and customer validation research will be essential for confirming demand and sizing opportunities.",
        
        "competition_analysis": f"Competitive Positioning: {differentiation}\n\nThe differentiation strategy outlined shows potential for competitive advantage. Continuous monitoring of competitive landscape and innovation will be key for maintaining market position.",
        
        "revenue_model_assessment": "Revenue model analysis pending detailed business model validation. Key considerations include pricing strategy, customer acquisition costs, and lifetime value optimization.",
        
        "resource_requirements": "Resource analysis indicates need for technical team, marketing investment, and operational infrastructure. Funding requirements will depend on growth strategy and market approach.",
        
        "key_risks": "Primary risks include market adoption challenges, competitive response, execution complexity, and resource requirements. Risk mitigation strategies should focus on rapid market validation and iterative development.",
        
        "go_to_market_strategy": "Go-to-market approach should emphasize customer development, product-market fit validation, and scalable acquisition channels. Digital marketing and strategic partnerships likely to be key success factors.",
        
        "financial_projections": "Financial framework should include revenue projections, customer acquisition cost analysis, and break-even modeling. Key metrics will include monthly recurring revenue growth and customer lifetime value.",
        
        "technology_assessment": "Technology feasibility appears strong based on solution description. Key considerations include scalability architecture, integration requirements, and development timeline.",
        
        "strengths": [
            "Clear problem identification with market relevance",
            "Innovative solution approach with differentiation potential", 
            "Founder understanding of target market needs"
        ],
        
        "weaknesses": [
            "Market validation still required for demand confirmation",
            "Competitive landscape analysis needs deeper research",
            "Resource requirements may be substantial for full execution"
        ],
        
        "opportunities": [
            "Growing market trend toward entrepreneurship and solo ventures",
            "Technology advancement enabling new solution approaches",
            "Potential for strategic partnerships and integrations"
        ],
        
        "threats": [
            "Established competitors with significant resources",
            "Market adoption challenges for new solution categories",
            "Economic conditions affecting target customer spending"
        ],
        
        "recommendations": [
            "Conduct detailed customer development interviews within 30 days",
            "Develop minimum viable product for market validation within 60 days",
            "Create financial model with realistic projections and funding requirements within 90 days"
        ],
        
        "next_steps": [
            "Interview 20+ potential customers to validate problem and solution fit",
            "Research competitive landscape and develop differentiation strategy",
            "Create business model canvas and financial projections for investor discussions"
        ]
    }

# ==========================================
# REPORT GENERATION FUNCTIONS
# ==========================================

def create_markdown_report() -> str:
    """Create comprehensive Markdown report with professional formatting."""
    idea = venture["idea"]
    responses = venture["responses"]
    analysis = venture["analysis"]
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    # Extract scoring with fallbacks
    overall_score = analysis.get('viability_score', 0)
    problem_fit = analysis.get('problem_solution_fit', 0)
    market_score = analysis.get('market_potential', 0)
    competitive_score = analysis.get('competitive_advantage', 0)
    revenue_score = analysis.get('revenue_potential', 0)
    execution_score = analysis.get('execution_feasibility', 0)
    
    # Generate score visualization
    score_bars = create_score_visualization(overall_score, problem_fit, market_score, competitive_score, revenue_score, execution_score)
    
    report = f"""---
title: "VentureLens Business Analysis Report"
subtitle: "{idea}"
author: "VentureLens AI Analysis Platform"
date: "{timestamp}"
geometry: 
  - margin=1in
  - letterpaper
documentclass: article
fontsize: 11pt
linestretch: 1.15
colorlinks: true
linkcolor: blue
urlcolor: blue
toccolor: black
toc: true
toc-depth: 3
numbersections: true
header-includes:
  - \\usepackage{{booktabs}}
  - \\usepackage{{xcolor}}
  - \\usepackage{{graphicx}}
  - \\usepackage{{fancyhdr}}
  - \\usepackage{{array}}
  - \\usepackage{{longtable}}
  - \\usepackage{{float}}
  - \\usepackage{{enumitem}}
  - \\setlist[itemize]{{leftmargin=*,topsep=0pt,parsep=0pt,partopsep=0pt}}
  - \\pagestyle{{fancy}}
  - \\fancyhead[L]{{VentureLens Analysis}}
  - \\fancyhead[R]{{\\thepage}}
  - \\fancyfoot[C]{{Confidential Business Analysis}}
  - \\definecolor{{scorecolor}}{{RGB}}{{52, 152, 219}}
  - \\definecolor{{excellent}}{{RGB}}{{39, 174, 96}}
  - \\definecolor{{good}}{{RGB}}{{243, 156, 18}}
  - \\definecolor{{moderate}}{{RGB}}{{230, 126, 34}}
  - \\definecolor{{poor}}{{RGB}}{{231, 76, 60}}
---

\\newpage

# Executive Summary

**Business Idea:** {idea}

**Overall Viability Score:** {overall_score}/10

**Assessment:** {get_score_assessment(overall_score)}

**Generated:** {timestamp}

---

## Scoring Breakdown

{score_bars}

| Dimension | Score | Assessment |
|-----------|-------|------------|
| **Overall Viability** | {overall_score}/10 | {get_score_assessment(overall_score)} |
| Problem-Solution Fit | {problem_fit}/10 | {get_score_assessment(problem_fit)} |
| Market Potential | {market_score}/10 | {get_score_assessment(market_score)} |
| Competitive Advantage | {competitive_score}/10 | {get_score_assessment(competitive_score)} |
| Revenue Potential | {revenue_score}/10 | {get_score_assessment(revenue_score)} |
| Execution Feasibility | {execution_score}/10 | {get_score_assessment(execution_score)} |

---

# Business Overview

## Problem Analysis
{analysis.get('problem_description', '*Based on interview responses - detailed analysis pending*')}

## Solution Description  
{analysis.get('solution_description', '*Based on interview responses - detailed analysis pending*')}

## Target Market Analysis
{analysis.get('target_market_analysis', '*Based on interview responses - detailed analysis pending*')}

## Competitive Landscape
{analysis.get('competition_analysis', '*Based on interview responses - detailed analysis pending*')}

## Revenue Model Assessment
{analysis.get('revenue_model_assessment', '*Based on interview responses - detailed analysis pending*')}

## Resource Requirements
{analysis.get('resource_requirements', '*Based on interview responses - detailed analysis pending*')}

## Risk Assessment
{analysis.get('key_risks', '*Based on interview responses - detailed analysis pending*')}

---

# Strategic Planning

## Go-to-Market Strategy
{analysis.get('go_to_market_strategy', '*Detailed go-to-market strategy analysis pending*')}

## Financial Projections Framework
{analysis.get('financial_projections', '*Revenue projections and financial modeling framework pending*')}

## Technology Assessment
{analysis.get('technology_assessment', '*Technical feasibility and architecture analysis pending*')}

---

# Market Research Intelligence

{venture.get('market_research', {}).get('summary', '> **Note:** Market research data temporarily unavailable. Analysis based on interview responses and business fundamentals.')}

---

# Strategic Analysis

## SWOT Analysis

### 💪 Strengths
{format_list_items(analysis.get("strengths", ["Analysis in progress..."]), "+")}

### ⚠️ Weaknesses  
{format_list_items(analysis.get("weaknesses", ["Analysis in progress..."]), "-")}

### 🚀 Opportunities
{format_list_items(analysis.get("opportunities", ["Analysis in progress..."]), "+")}

### 🛡️ Threats
{format_list_items(analysis.get("threats", ["Analysis in progress..."]), "-")}

---

# Recommendations & Next Steps

## 🎯 Strategic Recommendations
{format_list_items(analysis.get("recommendations", ["Analysis in progress..."]), "1")}

## 📋 Immediate Next Steps  
{format_list_items(analysis.get("next_steps", ["Analysis in progress..."]), "1")}

---

# Appendix

## Interview Responses
{format_interview_responses(responses)}

---

*Report generated by **VentureLens** - AI-Powered Business Analysis Platform*

*Powered by Praval's Multi-Agent Intelligence Framework*
"""
    
    return report

def create_score_visualization(overall, problem, market, competitive, revenue, execution):
    """Create LaTeX-compatible score visualization for better PDF formatting."""
    def make_bar(score, width=20):
        filled = int((score / 10) * width)
        empty = width - filled
        # Use LaTeX-friendly characters and ensure consistent alignment
        return "■" * filled + "□" * empty
    
    bars = f"""
```
Overall Viability:    {make_bar(overall)} {overall}/10
Problem-Solution Fit: {make_bar(problem)} {problem}/10  
Market Potential:     {make_bar(market)} {market}/10
Competitive Edge:     {make_bar(competitive)} {competitive}/10
Revenue Potential:    {make_bar(revenue)} {revenue}/10
Execution Feasibility:{make_bar(execution)} {execution}/10
```
"""
    return bars

def get_score_assessment(score):
    """Get qualitative assessment for numerical score."""
    if score >= 8.5:
        return "🟢 Excellent"
    elif score >= 7.0:
        return "🟡 Strong" 
    elif score >= 5.5:
        return "🟠 Moderate"
    elif score >= 3.0:
        return "🔴 Weak"
    else:
        return "⚫ Poor"

def format_list_items(items, style="•"):
    """Format list items with proper Markdown styling."""
    if not items or not isinstance(items, list):
        return "*Analysis in progress...*"
    
    if style == "1":
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
    elif style == "+":
        return "\n".join([f"+ **{item}**" for item in items])
    elif style == "-":
        return "\n".join([f"- *{item}*" for item in items])
    else:
        return "\n".join([f"• {item}" for item in items])

def format_interview_responses(responses):
    """Format interview responses for appendix."""
    if not responses:
        return "*No interview data available*"
    
    formatted = ""
    for key, value in responses.items():
        clean_key = key.replace("_", " ").title()
        formatted += f"\n**{clean_key}:**\n{value}\n"
    
    return formatted

def create_professional_pdf(markdown_content: str, filename: str):
    """Create professional PDF using Pandoc with LaTeX styling."""
    import subprocess
    import tempfile
    import os
    
    markdown_filename = filename.replace('.pdf', '.md')
    
    try:
        # Save Markdown file
        with open(markdown_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Try Pandoc with professional LaTeX template
        pandoc_cmd = [
            'pandoc',
            markdown_filename,
            '-o', filename,
            '--pdf-engine=xelatex',
            '--toc',
            '--number-sections',
            '--highlight-style=github',
            '--variable', 'geometry:margin=1in',
            '--variable', 'fontsize=11pt',
            '--variable', 'linestretch=1.2',
            '--variable', 'colorlinks=true',
            '--variable', 'linkcolor=blue',
            '--variable', 'urlcolor=blue',
            '--variable', 'citecolor=blue',
            '--variable', 'toccolor=black'
        ]
        
        result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"✅ Professional PDF generated with Pandoc: {filename}")
            # Keep markdown file for reference
            return filename
        else:
            logging.warning(f"Pandoc failed: {result.stderr}")
            raise Exception(f"Pandoc conversion failed: {result.stderr}")
            
    except FileNotFoundError:
        logging.warning("Pandoc not found, trying alternative PDF generation...")
        # Fallback to wkhtmltopdf with HTML conversion
        return create_html_pdf(markdown_content, filename)
        
    except Exception as e:
        logging.warning(f"Professional PDF generation failed: {e}")
        # Final fallback
        return create_html_pdf(markdown_content, filename)

def create_html_pdf(markdown_content: str, filename: str):
    """Fallback: Convert Markdown to HTML then PDF."""
    import subprocess
    import tempfile
    
    try:
        # Convert Markdown to HTML using basic approach
        html_content = markdown_to_html(markdown_content)
        html_filename = filename.replace('.pdf', '.html')
        
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Try wkhtmltopdf
        try:
            result = subprocess.run([
                'wkhtmltopdf',
                '--page-size', 'A4',
                '--margin-top', '1in',
                '--margin-bottom', '1in', 
                '--margin-left', '1in',
                '--margin-right', '1in',
                '--encoding', 'UTF-8',
                '--enable-local-file-access',
                html_filename, filename
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info(f"✅ PDF generated with wkhtmltopdf: {filename}")
                return filename
        except FileNotFoundError:
            pass
        
        # Keep HTML as final fallback
        logging.info(f"📄 HTML report generated: {html_filename}")
        return html_filename
        
    except Exception as e:
        # Final text fallback
        text_filename = filename.replace('.pdf', '.txt')
        with open(text_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logging.info(f"📄 Text report generated: {text_filename}")
        return text_filename

def markdown_to_html(markdown_content: str) -> str:
    """Simple Markdown to HTML conversion."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>VentureLens Business Analysis Report</title>
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6; 
                max-width: 800px; 
                margin: 0 auto; 
                padding: 40px 20px;
                color: #333;
            }}
            h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #34495e; border-left: 4px solid #3498db; padding-left: 15px; margin-top: 30px; }}
            h3 {{ color: #2c3e50; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #f8f9fa; font-weight: bold; }}
            blockquote {{ background: #f8f9fa; border-left: 4px solid #3498db; margin: 0; padding: 10px 20px; }}
            code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
            pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
            hr {{ border: none; height: 2px; background: #3498db; margin: 30px 0; }}
            .score-excellent {{ color: #27ae60; font-weight: bold; }}
            .score-good {{ color: #f39c12; font-weight: bold; }}
            .score-poor {{ color: #e74c3c; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div style="text-align: center; background: #3498db; color: white; padding: 20px; margin: -40px -20px 40px -20px;">
            <h1 style="color: white; border: none; margin: 0;">🔍 VentureLens</h1>
            <p style="margin: 5px 0 0 0; font-size: 18px;">AI-Powered Business Analysis Report</p>
        </div>
        {basic_markdown_to_html_conversion(markdown_content)}
    </body>
    </html>
    """
    return html_content

def basic_markdown_to_html_conversion(content: str) -> str:
    """Enhanced Markdown to HTML conversion with better formatting."""
    import re
    
    # Remove YAML front matter
    content = re.sub(r'^---.*?---\n', '', content, flags=re.DOTALL)
    
    # Handle Pandoc column syntax - convert to HTML div
    content = re.sub(r':::: \{\.columns\}.*?::::', '', content, flags=re.DOTALL)
    content = re.sub(r'::: \{\.column.*?\}.*?:::', '', content, flags=re.DOTALL)
    
    # Convert headers with better styling
    content = re.sub(r'^# (.*?)$', r'<h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">\1</h1>', content, flags=re.MULTILINE)
    content = re.sub(r'^## (.*?)$', r'<h2 style="color: #34495e; border-left: 4px solid #3498db; padding-left: 15px; margin-top: 30px;">\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^### (.*?)$', r'<h3 style="color: #2c3e50;">\1</h3>', content, flags=re.MULTILINE)
    
    # Convert tables
    def convert_table(match):
        lines = match.group(0).strip().split('\n')
        if len(lines) < 2:
            return match.group(0)
        
        table_html = '<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">'
        
        # Header row
        header = lines[0].split('|')[1:-1]  # Remove empty first/last elements
        table_html += '<tr>'
        for cell in header:
            table_html += f'<th style="border: 1px solid #ddd; padding: 12px; background: #f8f9fa;">{cell.strip()}</th>'
        table_html += '</tr>'
        
        # Data rows (skip separator line)
        for line in lines[2:]:
            if '|' in line:
                cells = line.split('|')[1:-1]
                table_html += '<tr>'
                for cell in cells:
                    table_html += f'<td style="border: 1px solid #ddd; padding: 12px;">{cell.strip()}</td>'
                table_html += '</tr>'
        
        table_html += '</table>'
        return table_html
    
    # Find and convert tables
    content = re.sub(r'\|[^\n]+\|\n\|[-\s|:]+\|\n(?:\|[^\n]+\|\n)*', convert_table, content, flags=re.MULTILINE)
    
    # Convert lists with better styling
    content = re.sub(r'^\+ \*\*(.*?)\*\*$', r'<li style="margin: 5px 0; color: #27ae60;"><strong>\1</strong></li>', content, flags=re.MULTILINE)
    content = re.sub(r'^- \*(.*?)\*$', r'<li style="margin: 5px 0; color: #e74c3c;"><em>\1</em></li>', content, flags=re.MULTILINE)
    content = re.sub(r'^(\d+)\. (.*)$', r'<li style="margin: 5px 0;">\2</li>', content, flags=re.MULTILINE)
    
    # Convert bold and italic
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
    
    # Convert code blocks with styling
    content = re.sub(r'```(.*?)```', r'<pre style="background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto;"><code>\1</code></pre>', content, flags=re.DOTALL)
    
    # Convert horizontal rules
    content = re.sub(r'^---$', r'<hr style="border: none; height: 2px; background: #3498db; margin: 30px 0;">', content, flags=re.MULTILINE)
    
    # Convert blockquotes
    content = re.sub(r'^> (.*)$', r'<blockquote style="background: #f8f9fa; border-left: 4px solid #3498db; margin: 0; padding: 10px 20px;">\1</blockquote>', content, flags=re.MULTILINE)
    
    # Convert paragraphs
    paragraphs = content.split('\n\n')
    formatted_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if para:
            # Don't wrap already formatted elements
            if not (para.startswith('<') or para.startswith('```')):
                para = f'<p style="margin: 15px 0; line-height: 1.6;">{para}</p>'
            formatted_paragraphs.append(para)
    
    content = '\n'.join(formatted_paragraphs)
    
    # Clean up multiple line breaks
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content

def auto_open_reports(filename: str):
    """Automatically open both HTML and PDF reports in browser tabs."""
    import webbrowser
    import os
    from pathlib import Path
    
    try:
        base_path = Path(filename).stem  # Remove extension
        
        # Look for both PDF and HTML versions
        pdf_file = f"{base_path}.pdf"
        html_file = f"{base_path}.html"
        
        files_opened = []
        
        # Try to open PDF first (if it exists)
        if os.path.exists(pdf_file):
            try:
                # Use file:// URL for local files
                pdf_url = f"file://{os.path.abspath(pdf_file)}"
                webbrowser.open_new_tab(pdf_url)
                files_opened.append(f"PDF: {pdf_file}")
                print(f"🌐 Opened PDF in browser: {pdf_file}")
            except Exception as e:
                print(f"⚠️ Could not open PDF in browser: {e}")
        
        # Try to open HTML (if it exists)
        if os.path.exists(html_file):
            try:
                # Use file:// URL for local files
                html_url = f"file://{os.path.abspath(html_file)}"
                webbrowser.open_new_tab(html_url)
                files_opened.append(f"HTML: {html_file}")
                print(f"🌐 Opened HTML in browser: {html_file}")
            except Exception as e:
                print(f"⚠️ Could not open HTML in browser: {e}")
        
        # If no files were found, try the original filename
        if not files_opened and os.path.exists(filename):
            try:
                file_url = f"file://{os.path.abspath(filename)}"
                webbrowser.open_new_tab(file_url)
                print(f"🌐 Opened report in browser: {filename}")
            except Exception as e:
                print(f"⚠️ Could not open report in browser: {e}")
        
        if files_opened:
            print(f"📋 Browser tabs opened for: {', '.join(files_opened)}")
        else:
            print("⚠️ No report files found to open in browser")
            
    except Exception as e:
        print(f"❌ Error opening reports in browser: {e}")

# ==========================================
# MAIN APPLICATION
# ==========================================

def start_venture_analysis(idea: str):
    """Start the business idea analysis process."""
    logging.info(f"🚀 Starting VentureLens analysis for: {idea}")
    
    # Clear state completely
    venture.clear()
    venture.update({
        "idea": idea,
        "responses": {},
        "analysis": {},
        "market_research": {},
        "questions_asked": 0,
        "max_questions": 20,
        "stage": "starting",
        "interview_started": False,
        "presentation_complete": False
    })
    
    # Start all agents - they self-organize through message types!
    start_agents(
        conduct_interview, conduct_market_research, analyze_business_viability, 
        generate_pdf_report, show_final_results,
        initial_data={"idea": idea, "type": "start_interview"},
        channel="venture"
    )

def wait_for_completion(timeout=120):
    """Wait for analysis to complete."""
    import time
    from praval import get_reef
    
    start_time = time.time()
    reef = get_reef()  # get_reef takes no arguments
    
    while venture["stage"] != "complete" and (time.time() - start_time) < timeout:
        # Handle interactive questions
        if venture["stage"] == "interviewing" and venture.get("current_question"):
            answer = input("Your answer: ").strip()
            if answer:
                # Send answer to interviewer using reef's system broadcast
                reef.system_broadcast({
                    "type": "answer_provided", 
                    "answer": answer, 
                    "question_key": venture["current_question"]
                }, "venture")  # channel as second argument
                venture["current_question"] = None
        
        time.sleep(0.5)
    
    return venture["stage"] == "complete"

def main():
    """VentureLens - AI Business Idea Analyzer."""
    print("🔍 VentureLens - AI Business Idea Analyzer")
    print("   Powered by Praval's Multi-Agent System")
    print("="*50)
    print("Get comprehensive analysis of your business ideas!")
    print()
    
    try:
        while True:
            idea = input("💡 Enter your business idea (or 'quit'): ").strip()
            if idea.lower() in ['quit', 'exit', 'q']:
                break
            
            if not idea:
                continue
            
            print(f"\n🚀 Analyzing: '{idea}'")
            print("="*50)
            
            start_venture_analysis(idea)
            success = wait_for_completion(timeout=300)  # 5 minutes timeout
            
            if not success:
                print("\n⏰ Analysis timed out or failed")
            
            print("\n" + "="*50)
            
            continue_prompt = input("\nAnalyze another idea? (y/N): ").strip().lower()
            if continue_prompt not in ['y', 'yes']:
                break
    
    except KeyboardInterrupt:
        print("\n👋 Thanks for using VentureLens!")

if __name__ == "__main__":
    main()
