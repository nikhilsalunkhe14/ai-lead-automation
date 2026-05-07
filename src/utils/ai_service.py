"""
AI Service - Professional AI integration for lead processing
"""

import logging
from typing import Dict, Any, Optional
from groq import Groq
from src.config.settings import settings
from src.services.context_service import get_context_service

class AIService:
    """Professional AI service for lead processing and scoring"""
    
    def __init__(self):
        self.client = None
        self.model = settings.GROQ_MODEL
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Groq client"""
        try:
            config = settings.get_ai_config()
            self.client = Groq(api_key=config['api_key'])
            logging.info("✅ AI client initialized successfully")
        except Exception as e:
            logging.error(f"❌ Failed to initialize AI client: {e}")
    
    def generate_lead_response(self, message: str) -> Dict[str, Any]:
        """Generate AI response and summary for lead message"""
        try:
            if not self.client:
                return {
                    'response': 'Thank you for your inquiry. We will get back to you soon.',
                    'summary': 'Standard lead inquiry'
                }
            
            # Create comprehensive prompt
            prompt = self._create_lead_processing_prompt(message)
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional AI assistant for a lead generation system. Analyze the lead message and provide appropriate responses."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            ai_content = response.choices[0].message.content
            
            # Parse response
            return self._parse_ai_response(ai_content)
            
        except Exception as e:
            logging.error(f"Error generating AI response: {e}")
            return {
                'response': 'Thank you for your inquiry. We will get back to you soon.',
                'summary': 'Lead inquiry - AI processing failed'
            }
    
    def generate_contextual_response(self, 
                                  message: str,
                                  client_id: Optional[str] = None,
                                  conversation_id: Optional[str] = None,
                                  max_context_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate context-aware AI response using memory retrieval
        
        Args:
            message: Current user message
            client_id: Optional client identifier
            conversation_id: Optional conversation identifier
            max_context_tokens: Maximum tokens for context
            
        Returns:
            Dictionary with response, context, and metadata
        """
        try:
            if not self.client:
                return {
                    'response': 'Thank you for your inquiry. We will get back to you soon.',
                    'context_used': False,
                    'context_summary': 'AI service unavailable'
                }
            
            # Build context using context service
            context_service = get_context_service()
            context_data = context_service.build_context_for_conversation(
                message=message,
                client_id=client_id,
                conversation_id=conversation_id,
                max_tokens=max_context_tokens
            )
            
            # Create context-aware prompt
            prompt = self._create_context_aware_prompt(message, context_data)
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_context_aware_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            ai_content = response.choices[0].message.content
            
            # Parse response
            parsed_response = self._parse_contextual_response(ai_content)
            
            # Add context metadata
            parsed_response.update({
                'context_used': len(context_data['context']) > 0,
                'context_data': context_data,
                'client_id': client_id,
                'conversation_id': conversation_id
            })
            
            return parsed_response
            
        except Exception as e:
            logging.error(f"Error generating contextual response: {e}")
            return {
                'response': 'Thank you for your inquiry. We will get back to you soon.',
                'context_used': False,
                'context_summary': 'Context generation failed',
                'error': str(e)
            }
    
    def score_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score lead based on AI analysis"""
        try:
            if not self.client:
                return self._basic_score(lead_data)
            
            # Create scoring prompt
            prompt = self._create_scoring_prompt(lead_data)
            
            # Generate score
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert lead scoring system. Analyze leads and provide detailed scoring."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            ai_content = response.choices[0].message.content
            return self._parse_score_response(ai_content)
            
        except Exception as e:
            logging.error(f"Error scoring lead: {e}")
            return self._basic_score(lead_data)
    
    def generate_lead_summary(self, leads: list) -> Dict[str, Any]:
        """Generate AI summary of multiple leads"""
        try:
            if not self.client or not leads:
                return {
                    'summary': 'No leads to summarize',
                    'insights': []
                }
            
            # Create summary prompt
            prompt = self._create_summary_prompt(leads)
            
            # Generate summary
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a business intelligence AI. Analyze lead data and provide insights."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.5
            )
            
            ai_content = response.choices[0].message.content
            return self._parse_summary_response(ai_content)
            
        except Exception as e:
            logging.error(f"Error generating lead summary: {e}")
            return {
                'summary': f'Summary of {len(leads)} leads',
                'insights': ['AI processing failed']
            }
    
    def _create_lead_processing_prompt(self, message: str) -> str:
        """Create prompt for lead processing"""
        return f"""
        Analyze this lead message and provide:
        1. A professional response to the lead
        2. A brief summary of the inquiry
        3. Key information extracted
        
        Lead Message: "{message}"
        
        Please respond in this format:
        RESPONSE: [Your professional response]
        SUMMARY: [Brief summary]
        KEY_INFO: [Key information extracted]
        """
    
    def _create_scoring_prompt(self, lead_data: Dict[str, Any]) -> str:
        """Create prompt for lead scoring"""
        return f"""
        Score this lead on a scale of 0-100 based on:
        - Message quality and detail
        - Contact information completeness
        - Urgency indicators
        - Budget potential
        - Professionalism
        
        Lead Data:
        Name: {lead_data.get('name', 'N/A')}
        Email: {lead_data.get('email', 'N/A')}
        Phone: {lead_data.get('phone', 'N/A')}
        Company: {lead_data.get('company', 'N/A')}
        Message: {lead_data.get('message', 'N/A')}
        
        Please respond in this format:
        SCORE: [0-100]
        CONFIDENCE: [0-100]
        FACTORS: [List of scoring factors]
        RECOMMENDATION: [Action recommendation]
        """
    
    def _create_summary_prompt(self, leads: list) -> str:
        """Create prompt for lead summary"""
        lead_info = []
        for i, lead in enumerate(leads[:10]):  # Limit to 10 leads
            lead_info.append(f"{i+1}. {lead.get('name', 'N/A')} - {lead.get('company', 'N/A')} - {lead.get('status', 'N/A')}")
        
        return f"""
        Analyze these leads and provide insights:
        {chr(10).join(lead_info)}
        
        Please provide:
        1. Overall summary
        2. Key trends
        3. Actionable insights
        4. Priority recommendations
        
        Respond in this format:
        SUMMARY: [Overall summary]
        TRENDS: [Key trends observed]
        INSIGHTS: [Actionable insights]
        PRIORITIES: [Priority recommendations]
        """
    
    def _parse_ai_response(self, ai_content: str) -> Dict[str, Any]:
        """Parse AI response into structured data"""
        try:
            lines = ai_content.split('\n')
            response = ''
            summary = ''
            key_info = ''
            
            for line in lines:
                if line.startswith('RESPONSE:'):
                    response = line.replace('RESPONSE:', '').strip()
                elif line.startswith('SUMMARY:'):
                    summary = line.replace('SUMMARY:', '').strip()
                elif line.startswith('KEY_INFO:'):
                    key_info = line.replace('KEY_INFO:', '').strip()
            
            return {
                'response': response or 'Thank you for your inquiry. We will contact you soon.',
                'summary': summary or 'Lead inquiry received',
                'key_info': key_info or 'Basic inquiry'
            }
        except Exception as e:
            logging.error(f"Error parsing AI response: {e}")
            return {
                'response': 'Thank you for your inquiry. We will contact you soon.',
                'summary': 'Lead inquiry received'
            }
    
    def _parse_score_response(self, ai_content: str) -> Dict[str, Any]:
        """Parse AI scoring response"""
        try:
            lines = ai_content.split('\n')
            score = 50
            confidence = 50
            factors = []
            recommendation = 'Standard follow-up'
            
            for line in lines:
                if line.startswith('SCORE:'):
                    score = int(line.replace('SCORE:', '').strip())
                elif line.startswith('CONFIDENCE:'):
                    confidence = int(line.replace('CONFIDENCE:', '').strip())
                elif line.startswith('FACTORS:'):
                    factors = line.replace('FACTORS:', '').strip().split(', ')
                elif line.startswith('RECOMMENDATION:'):
                    recommendation = line.replace('RECOMMENDATION:', '').strip()
            
            return {
                'score': min(100, max(0, score)),
                'confidence': min(100, max(0, confidence)),
                'factors': factors,
                'recommendation': recommendation
            }
        except Exception as e:
            logging.error(f"Error parsing score response: {e}")
            return self._basic_score({})
    
    def _parse_summary_response(self, ai_content: str) -> Dict[str, Any]:
        """Parse AI summary response"""
        try:
            lines = ai_content.split('\n')
            summary = ''
            trends = []
            insights = []
            priorities = []
            
            for line in lines:
                if line.startswith('SUMMARY:'):
                    summary = line.replace('SUMMARY:', '').strip()
                elif line.startswith('TRENDS:'):
                    trends = line.replace('TRENDS:', '').strip().split(', ')
                elif line.startswith('INSIGHTS:'):
                    insights = line.replace('INSIGHTS:', '').strip().split(', ')
                elif line.startswith('PRIORITIES:'):
                    priorities = line.replace('PRIORITIES:', '').strip().split(', ')
            
            return {
                'summary': summary or 'Lead analysis complete',
                'trends': trends,
                'insights': insights,
                'priorities': priorities
            }
        except Exception as e:
            logging.error(f"Error parsing summary response: {e}")
            return {
                'summary': 'Lead analysis complete',
                'trends': [],
                'insights': [],
                'priorities': []
            }
    
    def _basic_score(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic scoring without AI"""
        score = 0
        factors = []
        
        # Message length
        message = lead_data.get('message', '')
        if len(message) > 100:
            score += 15
            factors.append('Detailed message')
        elif len(message) > 50:
            score += 8
            factors.append('Moderate detail')
        
        # Contact completeness
        if lead_data.get('phone'):
            score += 10
            factors.append('Phone provided')
        
        if lead_data.get('company'):
            score += 15
            factors.append('Company provided')
        
        # Email quality
        email = lead_data.get('email', '')
        if '@gmail.com' not in email and '@yahoo.com' not in email:
            score += 5
            factors.append('Professional email')
        
        # Urgency indicators
        urgent_words = ['urgent', 'asap', 'immediately', 'need', 'quickly']
        message_lower = message.lower()
        if any(word in message_lower for word in urgent_words):
            score += 10
            factors.append('Urgency indicated')
        
        return {
            'score': min(100, score),
            'confidence': 70,
            'factors': factors,
            'recommendation': 'Standard follow-up recommended'
        }
    
    def _create_context_aware_prompt(self, message: str, context_data: Dict[str, Any]) -> str:
        """
        Create context-aware prompt for AI response generation
        
        Args:
            message: Current user message
            context_data: Retrieved context data
            
        Returns:
            Enhanced prompt with context
        """
        context = context_data.get('context', [])
        context_summary = context_data.get('summary', '')
        
        # Build context section
        context_section = ""
        if context:
            context_parts = []
            for i, memory in enumerate(context[:5]):  # Limit to top 5 memories
                content = memory.get('content', '')[:200]  # Limit content length
                metadata = memory.get('metadata', {})
                retrieval_reason = memory.get('retrieval_reason', 'unknown')
                
                context_parts.append(
                    f"[Memory {i+1}] {content} "
                    f"(Type: {metadata.get('content_type', 'text')}, "
                    f"Similarity: {memory.get('similarity', 0):.2f}, "
                    f"Source: {retrieval_reason})"
                )
            
            context_section = f"\n\nRelevant Context:\n{chr(10).join(context_parts)}"
        
        # Create enhanced prompt
        prompt = f"""
Current Message: {message}

{context_section}

Context Summary: {context_summary}

Instructions:
1. Use the relevant context to provide a personalized, contextual response
2. Reference specific details from the context when appropriate
3. Maintain conversation continuity if this is a returning client
4. Ask intelligent follow-up questions based on the context
5. If no relevant context exists, provide a helpful general response

Please respond with:
RESPONSE: [Your personalized response]
FOLLOW_UP: [Any relevant follow-up questions or suggestions]
CONTEXT_USED: [How you used the context in your response]
"""
        
        return prompt
    
    def _get_context_aware_system_prompt(self) -> str:
        """Get system prompt for context-aware AI responses"""
        return """You are an intelligent AI assistant for a lead generation and CRM system with access to contextual memory. Your capabilities include:

1. **Memory Integration**: You have access to relevant past conversations, client information, and project details
2. **Personalization**: Use context to provide personalized, relevant responses
3. **Continuity**: Maintain conversation continuity and reference previous interactions
4. **Intelligence**: Ask intelligent follow-up questions based on context
5. **Professionalism**: Maintain professional, helpful tone while being contextually aware

Guidelines:
- Always acknowledge relevant context when present
- Reference specific details from past interactions when helpful
- Adapt your communication style based on client preferences
- Provide proactive suggestions based on project history
- Ask relevant questions that show you understand the client's needs
- If context is limited or irrelevant, gracefully transition to general assistance"""
    
    def _parse_contextual_response(self, ai_content: str) -> Dict[str, Any]:
        """
        Parse contextual AI response
        
        Args:
            ai_content: Raw AI response content
            
        Returns:
            Parsed response with components
        """
        try:
            lines = ai_content.split('\n')
            response = ''
            follow_up = ''
            context_used = ''
            
            for line in lines:
                if line.startswith('RESPONSE:'):
                    response = line.replace('RESPONSE:', '').strip()
                elif line.startswith('FOLLOW_UP:'):
                    follow_up = line.replace('FOLLOW_UP:', '').strip()
                elif line.startswith('CONTEXT_USED:'):
                    context_used = line.replace('CONTEXT_USED:', '').strip()
            
            return {
                'response': response or 'Thank you for your message. I appreciate you reaching out.',
                'follow_up': follow_up,
                'context_usage_note': context_used,
                'personalized': len(context) > 0
            }
        except Exception as e:
            logging.error(f"Error parsing contextual response: {e}")
            return {
                'response': ai_content or 'Thank you for your message.',
                'follow_up': '',
                'context_usage_note': 'Response parsing failed',
                'personalized': False
            }
