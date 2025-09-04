from pydantic import BaseModel, Field
from typing import Optional

class APIKeyValidationRequest(BaseModel):
    """Request model for API key validation"""
    apiKey: str = Field(..., description="The API key to validate")

class APIKeyValidationResponse(BaseModel):
    """Response model for API key validation"""
    success: bool = Field(..., description="Whether the request was successful")
    valid: bool = Field(..., description="Whether the API key is valid")
    message: str = Field(..., description="Validation message")
    provider: Optional[str] = Field(None, description="The provider name")