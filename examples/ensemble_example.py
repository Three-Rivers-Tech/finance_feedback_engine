"""
Ensemble Decision Engine Example

Demonstrates multi-provider ensemble mode with weighted voting.
Shows how multiple AI providers combine their decisions for more robust
trading recommendations.
"""

import yaml
from pathlib import Path
from finance_feedback_engine.core import FinanceFeedbackEngine
from rich.console import Console
from rich.table import Table

console = Console()


def load_ensemble_config():
    """Load ensemble configuration."""
    # Use test config with ensemble settings added
    config_path = Path("config/config.test.yaml")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Override to ensemble mode
    config['decision_engine'] = {
        'ai_provider': 'ensemble',
        'model_name': 'ensemble-v1',
        'decision_threshold': 0.7
    }
    
    # Add ensemble configuration
    config['ensemble'] = {
        'enabled_providers': ['local', 'cli', 'codex'],
        'provider_weights': {
            'local': 0.2,
            'cli': 0.4,
            'codex': 0.4
        },
        'voting_strategy': 'weighted',
        'agreement_threshold': 0.6,
        'adaptive_learning': True,
        'learning_rate': 0.1
    }
    
    return config


def demonstrate_ensemble():
    """Demonstrate ensemble decision making."""
    console.print("[bold blue]Ensemble Decision Engine Example[/bold blue]\n")
    
    # Load config
    config = load_ensemble_config()
    
    # Initialize engine
    console.print("[yellow]Initializing ensemble engine...[/yellow]")
    engine = FinanceFeedbackEngine(config)
    
    # Test assets
    test_assets = ['BTCUSD', 'ETHUSD']
    
    for asset in test_assets:
        console.print(f"\n[bold cyan]Analyzing {asset}[/bold cyan]")
        console.print("=" * 60)
        
        # Generate decision
        decision = engine.analyze_asset(asset)
        
        # Display main decision
        console.print(f"\n[bold green]Final Decision:[/bold green]")
        console.print(f"  Action: {decision['action']}")
        console.print(f"  Confidence: {decision['confidence']}%")
        console.print(f"  Amount: {decision.get('amount', 0):.6f}")
        
        # Display ensemble metadata
        if 'ensemble_metadata' in decision:
            meta = decision['ensemble_metadata']
            
            console.print(f"\n[bold yellow]Ensemble Analysis:[/bold yellow]")
            console.print(f"  Providers: {', '.join(meta['providers_used'])}")
            console.print(f"  Strategy: {meta['voting_strategy']}")
            console.print(f"  Agreement: {meta['agreement_score']:.1%}")
            console.print(f"  Confidence Variance: {meta['confidence_variance']:.1f}")
            
            # Create table for provider decisions
            table = Table(title="Provider Decisions")
            table.add_column("Provider", style="cyan")
            table.add_column("Action", style="green")
            table.add_column("Confidence", justify="right")
            table.add_column("Weight", justify="right", style="yellow")
            
            for provider, pdecision in meta['provider_decisions'].items():
                weight = meta['provider_weights'].get(provider, 0)
                table.add_row(
                    provider.upper(),
                    pdecision['action'],
                    f"{pdecision['confidence']}%",
                    f"{weight:.2f}"
                )
            
            console.print("\n")
            console.print(table)
            
            # Show voting results if available
            if 'action_votes' in decision:
                console.print(f"\n[bold]Action Votes:[/bold]")
                for action, vote_power in decision['action_votes'].items():
                    bar_length = int(vote_power * 30)
                    bar = "█" * bar_length
                    console.print(f"  {action:5s}: {bar} {vote_power:.2f}")


def demonstrate_weighted_vs_majority():
    """Compare weighted vs majority voting strategies."""
    console.print("\n\n[bold blue]Comparing Voting Strategies[/bold blue]\n")
    
    # Test with weighted voting
    console.print("[yellow]Strategy 1: Weighted Voting[/yellow]")
    config_weighted = load_ensemble_config()
    config_weighted['ensemble']['voting_strategy'] = 'weighted'
    
    engine_weighted = FinanceFeedbackEngine(config_weighted)
    decision_weighted = engine_weighted.analyze_asset('BTCUSD')
    
    console.print(f"  Decision: {decision_weighted['action']}")
    console.print(f"  Confidence: {decision_weighted['confidence']}%")
    
    # Test with majority voting
    console.print("\n[yellow]Strategy 2: Majority Voting[/yellow]")
    config_majority = load_ensemble_config()
    config_majority['ensemble']['voting_strategy'] = 'majority'
    
    engine_majority = FinanceFeedbackEngine(config_majority)
    decision_majority = engine_majority.analyze_asset('BTCUSD')
    
    console.print(f"  Decision: {decision_majority['action']}")
    console.print(f"  Confidence: {decision_majority['confidence']}%")
    
    # Test with stacking
    console.print("\n[yellow]Strategy 3: Stacking Ensemble[/yellow]")
    config_stacking = load_ensemble_config()
    config_stacking['ensemble']['voting_strategy'] = 'stacking'
    
    engine_stacking = FinanceFeedbackEngine(config_stacking)
    decision_stacking = engine_stacking.analyze_asset('BTCUSD')
    
    console.print(f"  Decision: {decision_stacking['action']}")
    console.print(f"  Confidence: {decision_stacking['confidence']}%")
    
    if 'meta_features' in decision_stacking:
        console.print(f"\n[bold]Meta-Features:[/bold]")
        for feature, value in decision_stacking['meta_features'].items():
            if isinstance(value, float):
                console.print(f"  {feature}: {value:.3f}")
            else:
                console.print(f"  {feature}: {value}")


def demonstrate_provider_stats():
    """Show provider performance statistics."""
    console.print("\n\n[bold blue]Provider Performance Stats[/bold blue]\n")
    
    config = load_ensemble_config()
    engine = FinanceFeedbackEngine(config)
    
    # Access ensemble manager from decision engine
    ensemble_manager = engine.decision_engine.ensemble_manager
    
    if ensemble_manager:
        stats = ensemble_manager.get_provider_stats()
        
        console.print("[yellow]Current Configuration:[/yellow]")
        console.print(f"  Enabled: {', '.join(stats['enabled_providers'])}")
        console.print(f"  Strategy: {stats['voting_strategy']}")
        
        console.print("\n[yellow]Provider Weights:[/yellow]")
        for provider, weight in stats['current_weights'].items():
            bar_length = int(weight * 40)
            bar = "▓" * bar_length
            console.print(f"  {provider:6s}: {bar} {weight:.2f}")
        
        if stats['provider_performance']:
            console.print("\n[yellow]Historical Performance:[/yellow]")
            table = Table()
            table.add_column("Provider", style="cyan")
            table.add_column("Accuracy", style="green", justify="right")
            table.add_column("Total Decisions", justify="right")
            table.add_column("Correct", justify="right")
            
            for provider, perf in stats['provider_performance'].items():
                table.add_row(
                    provider.upper(),
                    perf['accuracy'],
                    str(perf['total_decisions']),
                    str(perf['correct_decisions'])
                )
            
            console.print(table)
        else:
            console.print("\n[dim]No performance history yet[/dim]")


if __name__ == "__main__":
    console.print("""
[bold cyan]╔══════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║  Finance Feedback Engine 2.0 - Ensemble Mode Demo       ║[/bold cyan]
[bold cyan]╚══════════════════════════════════════════════════════════╝[/bold cyan]

This example demonstrates:
1. Multi-provider ensemble decision making
2. Weighted voting with adaptive learning
3. Different voting strategies (weighted, majority, stacking)
4. Provider performance tracking

""")
    
    try:
        # Main demonstration
        demonstrate_ensemble()
        
        # Compare strategies
        demonstrate_weighted_vs_majority()
        
        # Show stats
        demonstrate_provider_stats()
        
        console.print("\n[bold green]✓ Ensemble demo complete![/bold green]\n")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
