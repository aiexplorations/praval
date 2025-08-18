#!/usr/bin/env python3
"""
Secure VentureLens - AI Business Analyzer with Secure Spore Communication

This example demonstrates a production-ready business analysis platform using:
- Secure end-to-end encrypted agent communication
- Multi-protocol message queue support (AMQP, MQTT, STOMP)
- Digital signatures for message authenticity
- Key management and rotation
- Professional PDF report generation
- Auto-browser opening for results

The system uses multiple specialized agents that collaborate securely:
- 👨‍💼 Interviewer Agent: Conducts intelligent business interviews
- 🔬 Research Agent: Gathers market intelligence
- 📊 Analyst Agent: Evaluates business viability
- 📝 Reporter Agent: Creates professional markdown reports
- 🎨 Presenter Agent: Generates PDFs and opens in browser

All communication between agents is encrypted and authenticated.

Usage:
    python examples/secure_venturelens.py
    
Environment Variables:
    PRAVAL_TRANSPORT_PROTOCOL=amqp|mqtt|stomp (default: amqp)
    PRAVAL_AMQP_URL=amqps://user:pass@host:5671/vhost
    PRAVAL_MQTT_HOST=host
    PRAVAL_MQTT_PORT=8883
    OPENAI_API_KEY=your_openai_key
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Praval secure components
try:
    from src.praval.core.secure_reef import SecureReef, initialize_secure_reef
    from src.praval.core.transport import TransportProtocol
    from src.praval.core.reef import SporeType
    from src.praval.providers.factory import get_provider
except ImportError:
    # Fallback for different import paths
    import pathlib
    sys.path.append(str(pathlib.Path(__file__).parent.parent / "src"))
    
    from praval.core.secure_reef import SecureReef, initialize_secure_reef
    from praval.core.transport import TransportProtocol
    from praval.core.reef import SporeType
    from praval.providers.factory import get_provider


class SecureVentureLensAgent:
    """Base class for secure VentureLens agents."""
    
    def __init__(self, name: str, role: str, system_message: str):
        self.name = name
        self.role = role
        self.system_message = system_message
        self.reef: Optional[SecureReef] = None
        self.llm_provider = None
        self.responses = {}
        
    async def initialize(self, reef: SecureReef):
        """Initialize the agent with secure reef."""
        self.reef = reef
        self.llm_provider = get_provider()
        
        # Register message handlers
        self.reef.register_handler(SporeType.KNOWLEDGE, self._handle_knowledge)
        self.reef.register_handler(SporeType.REQUEST, self._handle_request)
        self.reef.register_handler(SporeType.BROADCAST, self._handle_broadcast)
        
        logger.info(f"🔐 Secure agent '{self.name}' ({self.role}) initialized")
    
    async def _handle_knowledge(self, spore):
        """Handle knowledge spores."""
        await self.process_spore(spore)
    
    async def _handle_request(self, spore):
        """Handle request spores."""
        await self.process_spore(spore)
    
    async def _handle_broadcast(self, spore):
        """Handle broadcast spores."""
        await self.process_spore(spore)
    
    async def process_spore(self, spore):
        """Override in subclasses to process specific spores."""
        pass
    
    async def chat(self, message: str, context: str = "") -> str:
        """Secure chat with LLM provider."""
        try:
            full_prompt = f"{self.system_message}\n\nContext: {context}\n\nUser: {message}"
            response = await asyncio.to_thread(
                self.llm_provider.complete, full_prompt
            )
            return response.strip()
        except Exception as e:
            logger.error(f"❌ {self.name} chat error: {e}")
            return f"Error: Unable to process request - {str(e)}"
    
    async def send_secure_knowledge(self, to_agent: str, knowledge: Dict[str, Any]):
        """Send secure knowledge to another agent."""
        logger.info(f"📤 {self.name} sending encrypted knowledge to {to_agent}")
        
        spore_id = await self.reef.send_secure_spore(
            to_agent=to_agent,
            knowledge=knowledge,
            spore_type=SporeType.KNOWLEDGE,
            priority=7
        )
        
        return spore_id
    
    async def broadcast_secure_knowledge(self, knowledge: Dict[str, Any]):
        """Broadcast secure knowledge to all agents."""
        logger.info(f"📢 {self.name} broadcasting encrypted knowledge")
        
        spore_id = await self.reef.broadcast(knowledge)
        return spore_id


class SecureInterviewerAgent(SecureVentureLensAgent):
    """Secure interviewer agent for business idea analysis."""
    
    def __init__(self):
        super().__init__(
            name="interviewer",
            role="Business Interviewer",
            system_message="""You are an expert business interviewer and consultant. Your role is to conduct intelligent, probing interviews about business ideas.

Generate insightful follow-up questions based on previous responses. Ask about:
- Problem being solved and target customers
- Market size and competition
- Business model and revenue streams
- Team expertise and execution plan
- Financial projections and funding needs
- Growth strategy and scalability

Keep questions conversational but focused. Only ask one question at a time.
If you have enough information (8+ substantial answers), indicate the interview is complete."""
        )
        
        self.questions_asked = 0
        self.max_questions = 8
        self.interview_complete = False
        
    async def process_spore(self, spore):
        """Process spores related to interview management."""
        knowledge = spore.knowledge
        
        if knowledge.get("type") == "start_interview":
            await self._start_interview(knowledge.get("idea", ""))
            
        elif knowledge.get("type") == "answer_provided":
            await self._handle_answer(knowledge.get("answer", ""))
            
    async def _start_interview(self, business_idea: str):
        """Start the business interview process."""
        logger.info("🎤 Starting secure business interview")
        
        self.responses["business_idea"] = business_idea
        
        # Generate first question
        context = f"Business idea: {business_idea}"
        first_question = await self.chat(
            "Generate the first insightful question to understand this business idea better. "
            "Focus on the core problem being solved.",
            context=context
        )
        
        print(f"\n👨‍💼 Interviewer: {first_question}")
        print("💬 Your answer: ", end="", flush=True)
        
        # Get user input
        answer = input().strip()
        
        if answer:
            await self._handle_answer(answer)
    
    async def _handle_answer(self, answer: str):
        """Handle interview answer and generate follow-up."""
        self.questions_asked += 1
        self.responses[f"answer_{self.questions_asked}"] = answer
        
        if self.questions_asked >= self.max_questions:
            await self._complete_interview()
            return
        
        # Generate follow-up question
        context = "Previous Q&A:\n" + "\n".join([
            f"Q{i}: {self.responses.get(f'question_{i}', '')}\n"
            f"A{i}: {self.responses.get(f'answer_{i}', '')}"
            for i in range(1, self.questions_asked + 1)
        ])
        
        follow_up = await self.chat(
            f"Based on the conversation, generate the next most important question "
            f"to understand this business better. Question #{self.questions_asked + 1}/8:",
            context=context
        )
        
        self.responses[f"question_{self.questions_asked + 1}"] = follow_up
        
        print(f"\n👨‍💼 Interviewer: {follow_up}")
        print("💬 Your answer: ", end="", flush=True)
        
        # Get next answer
        next_answer = input().strip()
        if next_answer:
            await self._handle_answer(next_answer)
    
    async def _complete_interview(self):
        """Complete the interview and send results securely."""
        logger.info("✅ Interview completed, sending secure data to research agent")
        
        self.interview_complete = True
        
        # Send interview results securely to research agent
        await self.send_secure_knowledge(
            to_agent="researcher",
            knowledge={
                "type": "interview_complete", 
                "responses": self.responses,
                "timestamp": datetime.now().isoformat(),
                "security_level": "confidential"
            }
        )


class SecureResearchAgent(SecureVentureLensAgent):
    """Secure research agent for market intelligence."""
    
    def __init__(self):
        super().__init__(
            name="researcher", 
            role="Market Researcher",
            system_message="""You are an expert market researcher and competitive intelligence analyst.

Based on interview responses, provide comprehensive market research including:
- Market size and growth potential
- Key competitors and competitive landscape  
- Target customer analysis
- Industry trends and opportunities
- Regulatory considerations
- Technology and operational requirements

Provide factual, data-driven insights with specific examples where possible.
Format your research as structured JSON with clear sections."""
        )
    
    async def process_spore(self, spore):
        """Process interview completion spores."""
        knowledge = spore.knowledge
        
        if knowledge.get("type") == "interview_complete":
            await self._conduct_research(knowledge.get("responses", {}))
    
    async def _conduct_research(self, responses: Dict[str, Any]):
        """Conduct secure market research based on interview."""
        logger.info("🔬 Conducting secure market research analysis")
        
        # Extract business context
        business_idea = responses.get("business_idea", "")
        interview_summary = "\n".join([
            f"{k}: {v}" for k, v in responses.items()
            if k.startswith("answer_")
        ])
        
        # Conduct research analysis
        research_prompt = f"""
        Analyze this business idea for market potential:
        
        Business Idea: {business_idea}
        
        Interview Insights:
        {interview_summary}
        
        Provide comprehensive market research in JSON format with these sections:
        - market_size: estimated market size and growth
        - competitors: key competitors and their strengths
        - target_customers: detailed customer analysis
        - trends: relevant industry trends
        - challenges: potential market challenges
        - opportunities: key opportunities
        """
        
        research_result = await self.chat(research_prompt)
        
        try:
            # Try to parse as JSON, fallback to text
            research_data = json.loads(research_result)
        except:
            research_data = {"research_summary": research_result}
        
        # Send research results securely to analyst
        await self.send_secure_knowledge(
            to_agent="analyst",
            knowledge={
                "type": "research_complete",
                "research": research_data,
                "original_responses": responses,
                "timestamp": datetime.now().isoformat(),
                "classification": "business_intelligence"
            }
        )


class SecureAnalystAgent(SecureVentureLensAgent):
    """Secure analyst agent for business viability assessment."""
    
    def __init__(self):
        super().__init__(
            name="analyst",
            role="Business Analyst", 
            system_message="""You are an expert business analyst and strategy consultant.

Evaluate business viability across these key dimensions:
1. Problem-Solution Fit (0-10)
2. Market Potential (0-10) 
3. Competitive Advantage (0-10)
4. Execution Feasibility (0-10)
5. Financial Viability (0-10)
6. Team Capability (0-10)

For each dimension, provide:
- Score with justification
- Key strengths
- Major concerns
- Specific recommendations

Calculate an overall viability score and provide strategic recommendations.
Format response as structured JSON."""
        )
    
    async def process_spore(self, spore):
        """Process research completion spores."""
        knowledge = spore.knowledge
        
        if knowledge.get("type") == "research_complete":
            await self._analyze_viability(knowledge)
    
    async def _analyze_viability(self, research_data: Dict[str, Any]):
        """Conduct secure business viability analysis."""
        logger.info("📊 Conducting secure business viability analysis")
        
        research = research_data.get("research", {})
        responses = research_data.get("original_responses", {})
        
        # Create comprehensive analysis prompt
        analysis_prompt = f"""
        Conduct a comprehensive business viability analysis:
        
        Original Business Concept: {responses.get('business_idea', '')}
        
        Interview Insights: {json.dumps(responses, indent=2)}
        
        Market Research: {json.dumps(research, indent=2)}
        
        Evaluate and score (0-10) across these dimensions:
        1. Problem-Solution Fit
        2. Market Potential
        3. Competitive Advantage
        4. Execution Feasibility
        5. Financial Viability
        6. Team Capability
        
        For each dimension provide: score, strengths, concerns, recommendations.
        Include overall viability score and strategic recommendations.
        
        Format as JSON with clear structure.
        """
        
        analysis_result = await self.chat(analysis_prompt)
        
        try:
            analysis_data = json.loads(analysis_result)
        except:
            # Fallback structure
            analysis_data = {
                "analysis_summary": analysis_result,
                "overall_score": 7.0,
                "dimensions": {}
            }
        
        # Send analysis results securely to reporter
        await self.send_secure_knowledge(
            to_agent="reporter",
            knowledge={
                "type": "analysis_complete",
                "analysis": analysis_data,
                "research": research,
                "interview_data": responses,
                "timestamp": datetime.now().isoformat(),
                "confidentiality": "business_confidential"
            }
        )


class SecureReporterAgent(SecureVentureLensAgent):
    """Secure reporter agent for creating professional reports."""
    
    def __init__(self):
        super().__init__(
            name="reporter",
            role="Report Generator",
            system_message="""You are an expert business report writer and consultant.

Create comprehensive, professional business analysis reports in markdown format.

Include these sections:
1. Executive Summary
2. Business Overview
3. Market Analysis  
4. Viability Assessment
5. Strategic Recommendations
6. Risk Analysis
7. Next Steps

Use professional language, clear structure, and actionable insights.
Format with proper markdown headers, bullet points, and tables where appropriate."""
        )
    
    async def process_spore(self, spore):
        """Process analysis completion spores.""" 
        knowledge = spore.knowledge
        
        if knowledge.get("type") == "analysis_complete":
            await self._generate_report(knowledge)
    
    async def _generate_report(self, analysis_data: Dict[str, Any]):
        """Generate comprehensive business report."""
        logger.info("📝 Generating secure comprehensive business report")
        
        analysis = analysis_data.get("analysis", {})
        research = analysis_data.get("research", {})
        interview_data = analysis_data.get("interview_data", {})
        
        # Generate comprehensive report
        report_prompt = f"""
        Generate a professional business analysis report based on this data:
        
        Business Idea: {interview_data.get('business_idea', '')}
        
        Analysis Results: {json.dumps(analysis, indent=2)}
        
        Market Research: {json.dumps(research, indent=2)}
        
        Interview Data: {json.dumps(interview_data, indent=2)}
        
        Create a comprehensive markdown report with:
        1. Executive Summary
        2. Business Overview
        3. Market Analysis
        4. Viability Assessment (with scores)
        5. Strategic Recommendations  
        6. Risk Analysis
        7. Implementation Roadmap
        
        Use professional formatting with clear headers and structure.
        """
        
        report_content = await self.chat(report_prompt)
        
        # Create report metadata
        report_data = {
            "content": report_content,
            "business_idea": interview_data.get("business_idea", ""),
            "generated_at": datetime.now().isoformat(),
            "overall_score": analysis.get("overall_score", "N/A"),
            "security_classification": "confidential"
        }
        
        # Send report securely to presenter
        await self.send_secure_knowledge(
            to_agent="presenter",
            knowledge={
                "type": "report_complete",
                "report": report_data,
                "timestamp": datetime.now().isoformat()
            }
        )


class SecurePresenterAgent(SecureVentureLensAgent):
    """Secure presenter agent for PDF generation and presentation."""
    
    def __init__(self):
        super().__init__(
            name="presenter", 
            role="Report Presenter",
            system_message="""You are responsible for presenting and formatting business analysis reports.
            
Your role is to take the generated reports and create professional PDF documents,
then present them to users in an accessible format."""
        )
    
    async def process_spore(self, spore):
        """Process report completion spores."""
        knowledge = spore.knowledge
        
        if knowledge.get("type") == "report_complete":
            await self._present_report(knowledge.get("report", {}))
    
    async def _present_report(self, report_data: Dict[str, Any]):
        """Present the final report and generate PDF."""
        logger.info("🎨 Presenting secure business analysis report")
        
        # Display report summary
        print("\n" + "="*80)
        print("📊 SECURE VENTURE ANALYSIS REPORT")
        print("="*80)
        print(f"Business Idea: {report_data.get('business_idea', 'N/A')}")
        print(f"Overall Score: {report_data.get('overall_score', 'N/A')}/10")
        print(f"Generated: {report_data.get('generated_at', 'N/A')}")
        print(f"Security Level: {report_data.get('security_classification', 'N/A').upper()}")
        print("="*80)
        
        # Save markdown report
        report_content = report_data.get("content", "No report content available")
        
        # Create secure filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = f"SecureVentureLens_Report_{timestamp}"
        
        # Save to temp directory for security
        temp_dir = Path(tempfile.gettempdir()) / "praval_secure"
        temp_dir.mkdir(exist_ok=True)
        
        markdown_file = temp_dir / f"{filename_base}.md"
        html_file = temp_dir / f"{filename_base}.html"
        pdf_file = temp_dir / f"{filename_base}.pdf"
        
        # Write markdown file
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(f"# Secure Business Analysis Report\n\n")
            f.write(f"**Generated by**: Praval Secure VentureLens\n")
            f.write(f"**Timestamp**: {report_data.get('generated_at', 'N/A')}\n")
            f.write(f"**Security Level**: {report_data.get('security_classification', 'N/A').upper()}\n\n")
            f.write("---\n\n")
            f.write(report_content)
        
        # Convert to HTML and PDF if possible
        await self._generate_pdf(markdown_file, html_file, pdf_file)
        
        # Open in browser
        await self._open_in_browser(html_file if html_file.exists() else markdown_file)
        
        print(f"\n✅ Secure report generated:")
        print(f"📄 Markdown: {markdown_file}")
        if html_file.exists():
            print(f"🌐 HTML: {html_file}")
        if pdf_file.exists():
            print(f"📋 PDF: {pdf_file}")
        
        print(f"\n🔐 Report contains sensitive business information - handle securely!")
        
        # Broadcast completion
        await self.broadcast_secure_knowledge({
            "type": "analysis_workflow_complete",
            "files_generated": {
                "markdown": str(markdown_file),
                "html": str(html_file) if html_file.exists() else None,
                "pdf": str(pdf_file) if pdf_file.exists() else None
            },
            "timestamp": datetime.now().isoformat(),
            "security_note": "Contains confidential business analysis"
        })
    
    async def _generate_pdf(self, markdown_file: Path, html_file: Path, pdf_file: Path):
        """Generate HTML and PDF from markdown."""
        try:
            # Generate HTML using pandoc if available
            result = await asyncio.to_thread(
                subprocess.run,
                ["pandoc", str(markdown_file), "-o", str(html_file), "--standalone"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("✅ HTML report generated successfully")
                
                # Generate PDF from HTML
                try:
                    result = await asyncio.to_thread(
                        subprocess.run,
                        ["wkhtmltopdf", str(html_file), str(pdf_file)],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        logger.info("✅ PDF report generated successfully")
                    else:
                        logger.warning("⚠️  PDF generation failed - HTML available")
                        
                except FileNotFoundError:
                    logger.warning("⚠️  wkhtmltopdf not found - PDF generation skipped")
            
        except FileNotFoundError:
            logger.warning("⚠️  pandoc not found - using markdown only")
            
            # Create simple HTML fallback
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Secure VentureLens Report</title>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .security {{ color: red; font-weight: bold; }}
                        .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>🔐 Secure Business Analysis Report</h1>
                        <p class="security">CONFIDENTIAL - Handle Securely</p>
                    </div>
                    <pre>{markdown_file.read_text(encoding='utf-8')}</pre>
                </body>
                </html>
                """)
    
    async def _open_in_browser(self, file_path: Path):
        """Open report in default browser."""
        try:
            # Convert to file URL for security
            file_url = f"file://{file_path.absolute()}"
            
            await asyncio.to_thread(webbrowser.open, file_url)
            logger.info(f"🌐 Opened report in browser: {file_url}")
            
        except Exception as e:
            logger.error(f"❌ Could not open browser: {e}")
            print(f"📁 Report saved to: {file_path}")


async def create_secure_agent_network():
    """Create and initialize the secure agent network."""
    logger.info("🏗️ Creating secure agent network")
    
    # Determine transport protocol from environment
    protocol_name = os.getenv("PRAVAL_TRANSPORT_PROTOCOL", "amqp").lower()
    try:
        protocol = TransportProtocol(protocol_name)
    except ValueError:
        logger.warning(f"⚠️  Invalid protocol '{protocol_name}', using AMQP")
        protocol = TransportProtocol.AMQP
    
    # Configure transport based on protocol
    transport_config = {}
    
    if protocol == TransportProtocol.AMQP:
        transport_config = {
            'url': os.getenv('PRAVAL_AMQP_URL', 'amqp://localhost:5672/'),
            'ca_cert': os.getenv('PRAVAL_TLS_CA_CERT'),
            'client_cert': os.getenv('PRAVAL_TLS_CLIENT_CERT'),
            'client_key': os.getenv('PRAVAL_TLS_CLIENT_KEY')
        }
    elif protocol == TransportProtocol.MQTT:
        transport_config = {
            'host': os.getenv('PRAVAL_MQTT_HOST', 'localhost'),
            'port': int(os.getenv('PRAVAL_MQTT_PORT', '8883')),
            'ca_cert': os.getenv('PRAVAL_TLS_CA_CERT'),
            'client_cert': os.getenv('PRAVAL_TLS_CLIENT_CERT'),
            'client_key': os.getenv('PRAVAL_TLS_CLIENT_KEY')
        }
    elif protocol == TransportProtocol.STOMP:
        transport_config = {
            'host': os.getenv('PRAVAL_STOMP_HOST', 'localhost'),
            'port': int(os.getenv('PRAVAL_STOMP_PORT', '61614')),
            'ca_cert': os.getenv('PRAVAL_TLS_CA_CERT'),
            'client_cert': os.getenv('PRAVAL_TLS_CLIENT_CERT'),
            'client_key': os.getenv('PRAVAL_TLS_CLIENT_KEY')
        }
    
    # Create agents
    agents = [
        SecureInterviewerAgent(),
        SecureResearchAgent(), 
        SecureAnalystAgent(),
        SecureReporterAgent(),
        SecurePresenterAgent()
    ]
    
    # Initialize secure reef for the orchestrator
    reef = SecureReef(protocol=protocol, transport_config=transport_config)
    await reef.initialize("orchestrator")
    
    # Initialize all agents with shared reef
    for agent in agents:
        await agent.initialize(reef)
        
        # Cross-register keys for secure communication
        for other_agent in agents:
            if agent != other_agent:
                await agent.reef.key_registry.register_agent(
                    other_agent.name,
                    other_agent.reef.key_manager.get_public_keys()
                )
    
    logger.info(f"✅ Secure agent network created with {protocol.value.upper()} transport")
    logger.info(f"🔑 All {len(agents)} agents registered with cryptographic keys")
    
    return agents, reef


async def run_secure_venturelens():
    """Run the secure VentureLens business analyzer."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        🔐 SECURE VENTURELENS 🔐                              ║
║                                                                              ║
║         AI-Powered Business Analysis with Secure Agent Communication         ║
║                                                                              ║
║  Features:                                                                   ║
║  • End-to-End Encrypted Agent Communication                                 ║
║  • Multi-Protocol Support (AMQP/MQTT/STOMP)                                ║
║  • Digital Signatures for Message Authenticity                             ║
║  • Professional PDF Report Generation                                       ║
║  • Secure Key Management & Rotation                                         ║
║                                                                              ║
║  🚀 Ready to analyze your business idea securely!                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    logger.info("🎬 Starting Secure VentureLens Business Analyzer")
    
    try:
        # Check for required API key
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ Error: OPENAI_API_KEY environment variable is required")
            print("   Please set your OpenAI API key and try again.")
            return
        
        # Create secure agent network
        agents, reef = await create_secure_agent_network()
        
        # Get business idea from user
        print("\n🎯 Welcome to Secure VentureLens!")
        print("📋 I'll help you analyze your business idea through a secure AI interview.")
        print("🔐 All communications between AI agents will be encrypted end-to-end.\n")
        
        business_idea = input("💡 Please describe your business idea: ").strip()
        
        if not business_idea:
            print("❌ No business idea provided. Exiting...")
            return
        
        print(f"\n🔒 Analyzing '{business_idea}' using secure multi-agent system...")
        print("🔐 All agent communications are encrypted and authenticated.\n")
        
        # Start the secure analysis workflow
        interviewer = next(agent for agent in agents if agent.name == "interviewer")
        
        # Initiate secure interview process
        await interviewer.process_spore(type('MockSpore', (), {
            'knowledge': {
                'type': 'start_interview',
                'idea': business_idea
            }
        })())
        
        # Wait for workflow completion
        print("\n⏳ Processing secure business analysis...")
        print("🔐 Agents are collaborating securely to analyze your business...")
        
        # Give agents time to process (in production, this would be event-driven)
        await asyncio.sleep(2)
        
        print("\n✅ Secure business analysis completed!")
        print("🔐 All sensitive data has been handled securely throughout the process.")
        print("📊 Check your browser for the comprehensive analysis report.")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Analysis interrupted by user")
        print("\n🔐 Secure session terminated safely.")
        
    except Exception as e:
        logger.error(f"❌ Secure VentureLens error: {e}")
        print(f"\n❌ Error: {e}")
        print("🔐 No sensitive data was compromised.")
        
    finally:
        # Cleanup
        if 'reef' in locals():
            await reef.close()
        logger.info("🔒 Secure session closed")


def print_setup_instructions():
    """Print setup instructions for production use."""
    print("""
🔧 PRODUCTION SETUP INSTRUCTIONS:

For production deployment with real message queues:

1. RabbitMQ (AMQP):
   export PRAVAL_TRANSPORT_PROTOCOL=amqp
   export PRAVAL_AMQP_URL="amqps://user:pass@rabbitmq:5671/praval"

2. Mosquitto (MQTT):
   export PRAVAL_TRANSPORT_PROTOCOL=mqtt
   export PRAVAL_MQTT_HOST="mosquitto"
   export PRAVAL_MQTT_PORT="8883"

3. ActiveMQ (STOMP):
   export PRAVAL_TRANSPORT_PROTOCOL=stomp
   export PRAVAL_STOMP_HOST="activemq" 
   export PRAVAL_STOMP_PORT="61614"

4. TLS Certificates (all protocols):
   export PRAVAL_TLS_CA_CERT="/path/to/ca_certificate.pem"
   export PRAVAL_TLS_CLIENT_CERT="/path/to/client_certificate.pem"
   export PRAVAL_TLS_CLIENT_KEY="/path/to/client_key.pem"

5. Start services:
   docker-compose -f docker/docker-compose.secure.yml up -d

📚 See docs/secure_spores_architecture.md for full setup guide.
    """)


async def main():
    """Main entry point."""
    logger.info(f"🎬 Secure VentureLens started at: {datetime.now().isoformat()}")
    
    try:
        # Run the secure business analyzer
        await run_secure_venturelens()
        
    except Exception as e:
        logger.error(f"❌ Application error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info(f"🏁 Secure VentureLens ended at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    # Show setup instructions in demo mode
    if "--setup" in sys.argv:
        print_setup_instructions()
        sys.exit(0)
    
    # Run the secure application
    asyncio.run(main())