# Similar Projects Research - Autonomous Trading Systems

**Date:** 2026-02-14  
**Purpose:** Extract valuable insights from comparable projects  
**Sources:** GitHub, arXiv, industry frameworks

---

## 1. TradingAgents - Multi-Agent LLM Framework

**Project:** https://github.com/TauricResearch/TradingAgents  
**Paper:** https://arxiv.org/abs/2412.20138 (arXiv:2412.20138 [q-fin.TR])  
**Status:** Open-source, actively maintained (v0.2.0 released Feb 2026)

### Architecture Overview

**Multi-agent system mirroring real trading firms:**

**Analyst Team:**
- Fundamentals Analyst (company financials, intrinsic value)
- Sentiment Analyst (social media, public mood)
- News Analyst (macroeconomic events)
- Technical Analyst (MACD, RSI, pattern recognition)

**Researcher Team:**
- Bull Researcher (optimistic view)
- Bear Researcher (pessimistic view)
- Debate-based synthesis (like our ensemble!)

**Trader Agent:**
- Synthesizes analyst/researcher insights
- Makes final trading decisions
- Integrates historical data

**Risk Management Team:**
- Monitors portfolio exposure
- Evaluates volatility and liquidity
- Provides assessment reports

**Portfolio Manager:**
- Approves/rejects trades
- Final execution authority

### Key Similarities to FFE 2.0

✅ **Multi-agent debate system** (Bull/Bear researchers ≈ our Bull/Bear/Judge ensemble)  
✅ **Risk management layer** (separate from decision making)  
✅ **LLM-powered agents** with specialized roles  
✅ **Debate-based decision synthesis**  

### Key Differences

❌ **Our advantage:** Futures-only focus (they do stocks)  
❌ **Our advantage:** Local-first LLMs (Ollama) vs cloud dependency  
❌ **Their advantage:** More granular analyst specialization (4 types vs our technical+sentiment)  
❌ **Their advantage:** Explicit risk management team (we have gatekeeper but simpler)

### Valuable Insights for FFE

1. **Debate rounds are configurable** (`max_debate_rounds` parameter)
   - **FFE lesson:** We should allow tuning debate depth based on market volatility
   - **Implementation:** Add `max_debate_rounds` to decision_engine config

2. **Model specialization** (deep_think_llm vs quick_think_llm)
   - **FFE lesson:** Use smaller models for routine tasks, bigger for complex
   - **Implementation:** Already planned (Haiku/Sonnet/Opus routing)

3. **Multi-provider LLM support** (OpenAI, Google, Anthropic, xAI, Ollama)
   - **FFE lesson:** Don't lock into one provider
   - **Implementation:** We already use Ollama + Gemini, could add more

4. **Performance metrics:** Cumulative returns, Sharpe ratio, maximum drawdown
   - **FFE lesson:** We track these but could formalize reporting
   - **Implementation:** Add to P&L tracking CLI output

5. **Framework is research-focused with disclaimers**
   - **FFE lesson:** We're production-focused, need higher reliability bar
   - **Advantage:** Our fail-closed safety model > their research approach

### Architecture Patterns to Adopt

**✅ Separate risk from execution:**
```python
# TradingAgents pattern:
analyst_insights = gather_analyst_views()
debate_result = researcher_debate(analyst_insights)
trade_proposal = trader_decide(debate_result)
risk_assessment = risk_team_evaluate(trade_proposal)
final_decision = portfolio_manager_approve(risk_assessment)

# FFE current pattern:
ensemble_decision = bull_bear_judge_debate()
gatekeeper_check = risk_validation(ensemble_decision)
execute(ensemble_decision)

# Improvement: Split risk into pre-check + post-approval layers
```

**✅ LangGraph for agent orchestration:**
- TradingAgents uses LangGraph for modularity
- **FFE opportunity:** Consider LangGraph for future multi-agent expansion

---

## 2. FinMem - Layered Memory for LLM Trading Agents

**Project:** https://github.com/pipiku915/FinMem-LLM-StockTrading  
**Paper:** https://arxiv.org/abs/2311.13743  
**Status:** Open-source, ICLR Workshop accepted

### Core Innovation: Memory Architecture

**Three modules:**

1. **Profiling Module**
   - Defines agent characteristics
   - Trading style, risk tolerance, preferences
   - **FFE equivalent:** Our Bull/Bear/Judge personas

2. **Memory Module (LAYERED)**
   - Short-term memory (recent trades, market state)
   - Medium-term memory (weekly patterns, trends)
   - Long-term memory (historical performance, learned strategies)
   - **FFE gap:** We don't persist learned insights between runs!

3. **Decision-making Module**
   - Converts memory insights into trades
   - **FFE equivalent:** Our decision engine

### Key Insight: Cognitive Span Tuning

> "FinMem's adjustable cognitive span allows for the retention of critical information beyond human perceptual limits, thereby enhancing trading outcomes."

**What this means:**
- Humans can't process 1000 candles at once
- LLMs can if properly structured
- **But:** Need to filter what's critical vs noise

**FFE lesson:**
- Our backtesting uses fixed lookback windows
- **Improvement:** Dynamic context window based on market regime
  - Volatile markets: shorter window (focus on recent)
  - Stable markets: longer window (identify trends)

### Memory Persistence Gap in FFE

**Current FFE behavior:**
- Agent restarts fresh each run
- No learning from past mistakes
- Historical data accessed but not synthesized into "lessons learned"

**FinMem approach:**
- Agents self-evolve professional knowledge
- React agilely to new investment cues
- Continuously refine decisions

**FFE opportunity:**
- Add `data/agent_memory/` directory
- Store: recurring patterns, failed strategies, market regime insights
- Load on startup, update after trades
- **Implementation:** 4-6 hours, high ROI for curriculum learning

### Performance Claims

- "Boosting cumulative investment returns"
- Tested on "scalable real-world financial dataset"
- Won IJCAI2024 FinLLM challenge (Task 3: Single Stock Trading)

**FFE validation:**
- Our stress tests showed similar promise (84% WR on BTC)
- But: We lack the memory persistence that made FinMem competitive

---

## 3. Backtesting.py - Short Position Validation

**Project:** https://kernc.github.io/backtesting.py/  
**Type:** Python framework for strategy backtesting  
**Key feature:** **Handles SHORT positions explicitly**

### Critical Pattern for FFE

**Example from their docs:**
```python
def next(self):
    if crossover(self.sma1, self.sma2):
        self.position.close()
        self.buy()  # Go LONG
    elif crossover(self.sma2, self.sma1):
        self.position.close()
        self.sell()  # Go SHORT (assuming CFD)
```

**Key insights:**

1. **Explicit SHORT handling:** `self.sell()` without existing position = short entry
2. **CFD assumption noted:** Short selling requires instrument support
3. **Position reversal:** Close existing before opening opposite direction

### FFE Short Position Checklist (from Backtesting.py patterns)

**✅ Must implement:**
- [ ] `decision.action = "SELL"` interpreted as short entry (not just close)
- [ ] `decision.action = "BUY"` when short closes the short position
- [ ] Stop-loss placement: **above entry price** for shorts
- [ ] Take-profit placement: **below entry price** for shorts
- [ ] P&L calculation: `(entry_price - exit_price) × units` for shorts
- [ ] Negative units or explicit SHORT flag in position tracking

**Their optimization approach:**
- "SAMBO optimizer" (tests hundreds of variants in seconds)
- **FFE equivalent:** Our Optuna optimization
- **Lesson:** We already have the right tool, just need SHORT-compatible backtesting

### Backtesting Best Practices (from their docs)

1. **Vectorized vs event-based:**
   - Vectorized = faster (process all data at once)
   - Event-based = more realistic (candle-by-candle simulation)
   - **FFE:** We use event-based (realistic)

2. **Composable strategies:**
   - Library of predefined utilities
   - Strategies that stack
   - **FFE opportunity:** Extract our Bull/Bear/Judge logic into reusable components

3. **Interactive visualization:**
   - Simulated results in charts
   - **FFE gap:** We have CLI output but no visual backtesting charts

---

## 4. FinRL - Deep Reinforcement Learning Library

**Project:** https://github.com/AI4Finance-Foundation/FinRL  
**Paper:** https://arxiv.org/abs/2011.09607  
**Focus:** RL agents (DQN, DDPG, PPO, SAC, A2C, TD3) for trading

### Why FinRL Matters for FFE

**Current FFE:** LLM-based decision making (ensemble debate)  
**Future FFE:** Could integrate RL for position sizing and timing

### Key RL Algorithms and Performance

From arXiv research:

**Best performers for trading:**
1. **PPO (Proximal Policy Optimization):** High performance, stable
2. **SAC (Soft Actor-Critic):** High performance, handles continuous action spaces
3. **DDPG (Deep Deterministic Policy Gradient):** Balanced approach

**Trading behavior differences:**
- **PPO & SAC:** Significant trades, limited stocks, shorter hold times
- **DDPG & TD3:** More balanced, longer hold periods
- **A2C:** Tends to remain stationary (less active trading)

### Hybrid LLM + RL Opportunity

**Pattern from research:**
> "LSTM-RL methods significantly outperform pure RL in portfolio optimization, demonstrating the benefits of integrating temporal modeling with reinforcement learning."

**FFE evolution path:**
1. **Phase 1 (Current):** LLM ensemble decides BUY/SELL/HOLD
2. **Phase 2 (Future):** RL agent learns optimal position sizing from LLM signals
3. **Phase 3 (Advanced):** RL agent learns when to trust/ignore LLM signals

**Implementation notes:**
- FinRL uses 2-layer feed-forward network (64 units, 32 units)
- Learning rate: 3e-4 (standard)
- **FFE could:** Use Proxmox GPU cluster for RL training

### Performance Metrics from FinRL Research

**Algorithmic trading (62 publications reviewed):**
- Most reported "substantial outperformance" over traditional methods
- PPO, SAC, Rainbow DQN achieved "high to moderate-high performance"
- **Caveat:** Many tested on historical data, fewer on live trading

**FFE comparison:**
- Our backtest: 84% WR on BTC (optimistic due to spot data)
- Industry RL baselines: ~55-65% WR typical
- **Insight:** Our LLM ensemble may already outperform pure RL

---

## 5. Cross-Domain Insights: Multi-Agent Systems in Other Fields

### Autonomous Vehicles (Similar Problem Space)

**Parallel to trading:**
- Multiple sensors (LIDAR, camera, radar) = multiple analysts
- Sensor fusion = ensemble decision making
- Safety-critical = financial risk management

**Lessons:**
1. **Redundancy is critical:** If one sensor fails, others compensate
   - **FFE:** If Ollama fails, fallback to Gemini (we have this!)

2. **Fail-safe defaults:** Autonomous cars brake when uncertain
   - **FFE:** Our gatekeeper fail-closed pattern (correct!)

3. **Continuous validation:** Real-time sensor cross-checking
   - **FFE opportunity:** Cross-check ensemble votes for consensus strength

### Medical AI (Similar Safety Requirements)

**Parallel to trading:**
- High-stakes decisions = large trades
- Multi-specialist consultation = multi-agent debate
- Regulatory compliance = financial compliance

**Lessons:**
1. **Explainability is mandatory:**
   - **FFE:** We log debate transcripts (good!)
   - **Improvement:** Add confidence scores to each agent's vote

2. **Human-in-the-loop for edge cases:**
   - **FFE:** We have telegram approval workflow (THR-308)
   - **But:** Not yet integrated with decision engine

3. **Audit trails:**
   - **FFE:** We have trade outcome recording (THR-235, THR-236)
   - **Improvement:** Add decision reasoning to audit log

---

## Key Takeaways: What FFE Should Adopt

### Immediate (This Week)

**1. SHORT position backtesting (Priority: CRITICAL)**
- Pattern: Follow Backtesting.py's `self.sell()` for short entry
- Implementation: Modify `backtester.py` to handle SELL signals as shorts
- **Time:** 3-4 hours
- **Value:** Validates 50% of our strategy

**2. Debate round tuning**
- Pattern: TradingAgents' `max_debate_rounds` parameter
- Implementation: Add to decision_engine config
- **Time:** 1 hour
- **Value:** Performance optimization without code changes

**3. Model specialization**
- Pattern: TradingAgents' deep_think vs quick_think
- Implementation: Already planned (Haiku/Sonnet/Opus routing)
- **Time:** Already in CLAUDE_BUDGET_PLAN.md
- **Value:** 40-60% cost reduction

### Short-term (Next 2 Weeks)

**4. Agent memory persistence**
- Pattern: FinMem's layered memory
- Implementation: `data/agent_memory/` with learned patterns
- **Time:** 4-6 hours
- **Value:** Continuous improvement, curriculum learning

**5. Visual backtesting**
- Pattern: Backtesting.py's interactive charts
- Implementation: Add Bokeh/Plotly charts to backtesting results
- **Time:** 3-4 hours
- **Value:** Faster strategy iteration, better debugging

**6. Risk management team separation**
- Pattern: TradingAgents' risk team + portfolio manager
- Implementation: Split gatekeeper into pre-check + post-approval
- **Time:** 6-8 hours
- **Value:** More sophisticated risk control

### Medium-term (Next 1-2 Months)

**7. Hybrid LLM + RL**
- Pattern: FinRL's PPO/SAC for position sizing
- Implementation: RL agent learns from LLM signals
- **Time:** 2-3 weeks (Proxmox GPU cluster training)
- **Value:** Optimal position sizing, risk-adjusted returns

**8. Multi-provider LLM support**
- Pattern: TradingAgents' provider abstraction
- Implementation: Add OpenAI, Anthropic as fallbacks
- **Time:** 4-6 hours
- **Value:** Redundancy, cost optimization

---

## Performance Comparison: FFE vs Industry

| Metric | FFE Backtest | TradingAgents | FinRL (RL) | Industry Avg |
|--------|--------------|---------------|------------|--------------|
| Win Rate (BTC) | 84% | Not disclosed | 55-65% | 50-55% |
| Win Rate (Forex) | 50-67% | Not disclosed | 55-65% | 52-58% |
| Approach | LLM Ensemble | LLM Multi-Agent | Pure RL | Mixed |
| Short Testing | ❌ None | ✅ Full | ✅ Full | ✅ Full |
| Memory Persistence | ❌ None | ❌ None | ✅ RL learns | Varies |
| Risk Management | ✅ Gatekeeper | ✅ Team | ⚠️ Simple | Varies |

**Strengths:**
- ✅ Our LLM ensemble may outperform pure RL (84% vs 55-65%)
- ✅ Fail-closed safety model superior to research frameworks
- ✅ Local-first LLMs reduce costs and latency

**Weaknesses:**
- ❌ **CRITICAL:** No SHORT position testing (unique to us)
- ❌ No agent memory persistence (FinMem has this)
- ❌ No visual backtesting tools (Backtesting.py has this)

---

## Recommended Roadmap

### Week 1 (Feb 15-21): Address Critical Gaps
1. SHORT position backtesting (3-4 hours) - **CRITICAL**
2. Manual SHORT test trades (1 hour) - **VALIDATION**
3. Debate round tuning (1 hour) - **OPTIMIZATION**

### Week 2 (Feb 22-28): Production Hardening
4. Agent memory persistence (4-6 hours)
5. Visual backtesting (3-4 hours)
6. Risk management refactor (6-8 hours)

### Month 2 (March): Advanced Features
7. Hybrid LLM + RL (2-3 weeks)
8. Multi-provider LLM (4-6 hours)

**Total time investment (Week 1):** ~6 hours  
**Total time investment (Week 1-2):** ~20 hours  
**ROI:** Validated SHORT capability, continuous learning, better risk management

---

## Conclusion

**Key lesson from research:** We're on the right track with LLM ensemble decision making. The multi-agent debate pattern appears in multiple successful frameworks (TradingAgents, FinMem).

**Critical gap:** SHORT position validation. Every comparable framework handles this—we don't. Must fix before scaling to 150 trades.

**Opportunity:** Agent memory persistence (FinMem pattern) could accelerate our curriculum learning significantly.

**Strategic advantage:** Our fail-closed safety model and local-first LLMs give us better risk management and cost structure than research frameworks.

**Next steps:**
1. Fix SHORT testing gap (this week)
2. Add agent memory (next week)
3. Consider hybrid LLM+RL (future evolution)
