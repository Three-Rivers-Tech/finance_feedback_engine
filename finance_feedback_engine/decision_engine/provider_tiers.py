"""Provider tier classification and asset-based routing for two-phase ensemble."""

from typing import Dict, List, Literal

# Free tier: 5 Ollama models + Qwen CLI (zero cost)
FREE_TIER = [
    'llama3.2:3b-instruct-fp16',
    'deepseek-r1:8b',
    'mistral:7b-instruct',
    'qwen2.5:7b-instruct',
    'gemma2:9b-instruct',
    'qwen'  # Qwen CLI (free tier with rate limits)
]

# Premium tier: Cloud-based APIs (require payment or limited free tier)
PREMIUM_TIER = [
    'gemini',  # Gemini CLI (free tier: 60/min, 1000/day)
    'cli',     # Copilot CLI (requires GitHub Copilot subscription)
    'codex'    # Codex CLI (fallback)
]

# VRAM requirements for Ollama models (in GB)
# All models selected to run on consumer GPU with 8GB VRAM
MODEL_VRAM_REQUIREMENTS: Dict[str, float] = {
    'llama3.2:3b-instruct-fp16': 3.2,
    'deepseek-r1:8b': 8.0,
    'mistral:7b-instruct': 7.0,
    'qwen2.5:7b-instruct': 7.0,
    'gemma2:9b-instruct': 7.5,  # 9B model fits in 8GB due to quantization
}

# Approximate download sizes (in GB)
MODEL_DOWNLOAD_SIZES: Dict[str, float] = {
    'llama3.2:3b-instruct-fp16': 3.2,
    'deepseek-r1:8b': 4.9,
    'mistral:7b-instruct': 4.1,
    'qwen2.5:7b-instruct': 4.4,
    'gemma2:9b-instruct': 5.4,
}


def get_free_providers() -> List[str]:
    """
    Get list of free-tier providers.
    
    Returns:
        List of provider names that are free to use
    """
    return FREE_TIER.copy()


def get_premium_providers() -> List[str]:
    """
    Get list of premium-tier providers.
    
    Returns:
        List of provider names that require payment or have strict limits
    """
    return PREMIUM_TIER.copy()


def get_ollama_models() -> List[str]:
    """
    Get list of Ollama models from free tier.
    
    Returns:
        List of Ollama model names (excludes CLI providers)
    """
    return [p for p in FREE_TIER if p != 'qwen']


def get_premium_provider_for_asset(asset_type: str) -> str:
    """
    Determine which premium provider to use based on asset type.
    
    Asset-based routing:
    - Crypto (BTC, ETH, etc.) -> Copilot CLI (best for crypto analysis)
    - Forex/Stock -> Gemini (best for traditional markets)
    
    Args:
        asset_type: Asset type from Alpha Vantage ('crypto', 'forex', 'stock')
    
    Returns:
        Premium provider name ('cli' for crypto, 'gemini' for forex/stock)
    
    Raises:
        ValueError: If asset_type is not one of the supported types
    """
    valid_types = ('crypto', 'forex', 'stock')
    if asset_type not in valid_types:
        raise ValueError(f"Invalid asset_type '{asset_type}'. Must be one of {valid_types}")
    
    if asset_type == 'crypto':
        return 'cli'
    else:
        # Forex and stock both use Gemini
        return 'gemini'


def get_fallback_provider() -> str:
    """
    Get the fallback premium provider (used when primary fails).
    
    Returns:
        Fallback provider name ('codex')
    """
    return 'codex'


def get_tier(provider_name: str) -> Literal['free', 'premium', 'unknown']:
    """
    Get the tier classification for a provider.
    
    Args:
        provider_name: Name of the provider
    
    Returns:
        'free', 'premium', or 'unknown'
    """
    if provider_name in FREE_TIER:
        return 'free'
    elif provider_name in PREMIUM_TIER:
        return 'premium'
    else:
        return 'unknown'


def is_ollama_model(provider_name: str) -> bool:
    """
    Check if provider is an Ollama model (vs CLI provider).
    
    Args:
        provider_name: Name of the provider
    
    Returns:
        True if Ollama model, False otherwise
    """
    return provider_name in MODEL_VRAM_REQUIREMENTS


def get_total_vram_required() -> float:
    """
    Calculate total VRAM if all models loaded simultaneously.
    Note: System loads models sequentially to avoid this.
    
    Returns:
        Total VRAM in GB
    """
    return sum(MODEL_VRAM_REQUIREMENTS.values())


def get_total_download_size() -> float:
    """
    Calculate total download size for all Ollama models.
    
    Returns:
        Total download size in GB
    """
    return sum(MODEL_DOWNLOAD_SIZES.values())
