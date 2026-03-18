# Performance Optimization Prompt Template

## Task Context
You are analyzing a FastAPI backend application for performance improvements. The application is a dermatology clinical decision support system that uses Ollama for AI inference.

## Analysis Requirements
When analyzing the codebase, consider:

1. **Database Performance**
   - Query optimization opportunities
   - Connection pooling
   - Caching strategies
   - N+1 query problems

2. **API Performance**
   - Response time optimization
   - Request/response serialization
   - Middleware efficiency
   - Route optimization

3. **AI Integration Performance**
   - Ollama model loading and inference optimization
   - Prompt engineering for faster responses
   - Caching AI responses
   - Batch processing opportunities

4. **Memory Management**
   - Memory leaks
   - Large object handling
   - Garbage collection optimization

5. **Concurrency**
   - Async/await usage
   - Thread safety
   - Resource contention

## Output Format
Provide specific, actionable recommendations with:
- File location and line numbers
- Before/after code examples
- Performance impact assessment
- Implementation complexity rating (Low/Medium/High)

## Multi-File Changes
When proposing changes that affect multiple files:
1. List all affected files
2. Provide implementation order
3. Include dependency considerations
4. Suggest testing strategy