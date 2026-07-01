import React, { useState, useRef, useEffect } from 'react';

import { motion, AnimatePresence, useScroll, useTransform, useMotionValue, useSpring } from 'framer-motion';

import { CADBlueprint } from './components/CADBlueprint';



// Premium CountUp Component for Fiscal Metric Vectors

const CoreNumericalCounter = ({ targetValue, duration = 1.8, structuralSuffix = "" }: { targetValue: number; duration?: number; structuralSuffix?: string }) => {

  const [currentCount, setCurrentCount] = useState(0);

  useEffect(() => {

    let startTime: number | null = null;

    const animateValue = (timestamp: number) => {

      if (!startTime) startTime = timestamp;

      const calculatedProgress = Math.min((timestamp - startTime) / (duration * 1000), 1);

      setCurrentCount(Math.floor(calculatedProgress * targetValue));

      if (calculatedProgress < 1) {

        requestAnimationFrame(animateValue);

      }

    };

    requestAnimationFrame(animateValue);

  }, [targetValue, duration]);



  return <span>{currentCount.toLocaleString('en-IN')}{structuralSuffix}</span>;

};



// Luxury Magnetic Hover Button Interface Wrap

const MagneticActionButton = ({ children, onClick, disabled = false, premiumClass = "" }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; premiumClass?: string }) => {

  const mouseAxisX = useMotionValue(0);

  const mouseAxisY = useMotionValue(0);

  

  const springConfig = { damping: 20, stiffness: 150, mass: 0.6 };

  const elasticX = useSpring(mouseAxisX, springConfig);

  const elasticY = useSpring(mouseAxisY, springConfig);



  const processMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {

    const { clientX, clientY, currentTarget } = e;

    const { left, top, width, height } = currentTarget.getBoundingClientRect();

    const centerX = left + width / 2;

    const centerY = top + height / 2;

    mouseAxisX.set((clientX - centerX) * 0.35);

    mouseAxisY.set((clientY - centerY) * 0.35);

  };



  const clearMagneticPull = () => {

    mouseAxisX.set(0);

    mouseAxisY.set(0);

  };



  return (

    <motion.button

      onClick={onClick}

      disabled={disabled}

      onMouseMove={processMouseMove}

      onMouseLeave={clearMagneticPull}

      style={{ x: elasticX, y: elasticY, position: 'relative', overflow: 'hidden' }}

      whileHover={{ scale: 1.015 }}

      whileTap={{ scale: 0.985 }}

      className={premiumClass}

    >

      {children}

    </motion.button>

  );

};



export default function App() {

  const [inputText, setInputText] = useState('I need a modern 3BHK house on a 1200 sq ft plot with parking, one pooja room and 2 floors.');

  const [isProcessing, setIsProcessing] = useState(false);

  const [loadingStepText, setLoadingStepText] = useState('Analyzing core requirements matrix...');

  const [matrixProgress, setMatrixProgress] = useState(0);

  const [backendPayload, setBackendPayload] = useState<any>(null);

  const [qaMemory, setQaMemory] = useState<any>({});

  const [qaTextInputs, setQaTextInputs] = useState<Record<string, string>>({});

  const [errorBanner, setErrorBanner] = useState<string | null>(null);



  // Structural References for Automated Camera Routing

  const sectionRefs = {

    hero: useRef<HTMLDivElement>(null),

    input: useRef<HTMLFieldSetElement>(null),

    optionA: useRef<HTMLDivElement>(null),

    optionB: useRef<HTMLDivElement>(null),

    comparison: useRef<HTMLFieldSetElement>(null),

    cost: useRef<HTMLFieldSetElement>(null),

    paint: useRef<HTMLFieldSetElement>(null),

    download: useRef<HTMLDivElement>(null),

  };



  const productionLogs = [

    "Analyzing input criteria metrics...",

    "Verifying missing spatial values...",

    "Planning circulatory patterns...",

    "Structuring room distributions...",

    "Plotting structural vector arrays...",

    "Drawing load-bearing perimeter walls...",

    "Placing door orientation nodes...",

    "Configuring lighting fenestration indices...",

    "Executing Vastu compliance pass...",

    "Estimating overall material budget configurations...",

    "Mapping architectural paint treatments...",

    "Compiling CAD vector package blocks..."

  ];



  // Continuous Micro-Drift Animation Sequence for Blueprint Background Grid

  const { scrollY } = useScroll();

  const backgroundSlowDriftY = useTransform(scrollY, [0, 4000], ["0px", "120px"]);



  const executeMatrixGeneration = async (updatedAnswers = qaMemory) => {

    if (!inputText || !inputText.trim()) {

      setErrorBanner("Requirement target matrix parameters are empty. Operational trace discarded.");

      return;

    }



    setIsProcessing(true);

    setErrorBanner(null);

    setMatrixProgress(4);

    

    let operationalIndex = 0;

    const trackingSequence = setInterval(() => {

      if (operationalIndex < productionLogs.length) {

        setLoadingStepText(productionLogs[operationalIndex]);

        setMatrixProgress(prev => Math.min(prev + 8, 94));

        operationalIndex++;

      }

    }, 380);



    try {

      // plot_width / plot_depth / floors_requested are deliberately NOT sent

      // here. They used to be hardcoded to 30 / 40 / 2 on every request,

      // which silently overrode whatever the user typed in the prompt or

      // answered in the clarification Q&A (qaMemory) below -- every

      // generation came out identical regardless of input. The backend

      // parses these straight out of user_prompt, or asks for them via

      // requires_clarification (current_answers carries those answers back).

      const response = await fetch('http://127.0.0.1:8000/api/generate', {

        method: 'POST',

        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },

        body: JSON.stringify({

          session_id: "sess-" + Date.now().toString(),

          user_prompt: inputText.trim(),

          plot_shape: "rectangle",

          current_answers: updatedAnswers

        })

      });

      

      clearInterval(trackingSequence);

      

      if (!response.ok) {

        throw new Error(`Calculation engine link synchronization failure. Server Exception Code: ${response.status}`);

      }

      

      const structuralPayload = await response.json();

      setMatrixProgress(100);

      setLoadingStepText("Vector layout structural trace finalized.");

      

      setTimeout(() => {

        setBackendPayload(structuralPayload);

        setIsProcessing(false);

        

        // Automated smooth viewport scroll execution directly to architectural results

        setTimeout(() => {

          if (structuralPayload?.options) {

            sectionRefs.optionA.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

          }

        }, 250);

      }, 400);



    } catch (err: any) {

      clearInterval(trackingSequence);

      setIsProcessing(false);

      setErrorBanner(err.message || "Failed to finalize sync pipeline channels to Aether computational mainframe.");

    }

  };



  const handleInteractiveAnswer = (fieldKey: string, chosenValue: string) => {

    const nextAnswers = { ...qaMemory, [fieldKey]: chosenValue };

    setQaMemory(nextAnswers);

    executeMatrixGeneration(nextAnswers);

  };



  // Shared Entry Viewport Logic Constants

  const viewportFadeSlideInConfig = {

    initial: { opacity: 0, y: 30, filter: 'blur(8px)' },

    whileInView: { opacity: 1, y: 0, filter: 'blur(0px)' },

    viewport: { once: true, margin: "-120px" },

    transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] }

  };



  return (

    <motion.div 

      className="blueprint-viewport-container"

      style={{ backgroundPositionY: backgroundSlowDriftY }}

    >

      <div className="blueprint-radial-mesh" />

      <div className="blueprint-vignette" />



      {/* LUXURY STUDIO HERO CONTAINER */}

      <section ref={sectionRefs.hero} style={{ textAlign: 'center', paddingTop: '160px', paddingBottom: '100px' }}>

        <div className="studio-content-width" style={{ maxWidth: '1000px' }}>

          

          {/* Architectural System Active Pulse Badge */}

          <motion.div 

            initial={{ opacity: 0, y: -15 }}

            animate={{ opacity: 1, y: 0 }}

            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}

            style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', backgroundColor: 'rgba(197, 168, 98, 0.03)', border: '1px solid rgba(197, 168, 98, 0.15)', padding: '8px 20px', borderRadius: '100px', marginBottom: '32px' }}

          >

            <motion.span 

              animate={{ opacity: [0.3, 1, 0.3], scale: [0.95, 1.05, 0.95] }}

              transition={{ repeat: Infinity, duration: 2.5, ease: 'easeInOut' }}

              style={{ width: '6px', height: '6px', backgroundColor: 'var(--gold-core)', borderRadius: '50%', boxShadow: '0 0 10px var(--gold-core)' }}

            />

            <span style={{ fontSize: '10.3px', fontWeight: 600, color: 'var(--gold-light)', letterSpacing: '0.18em', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Generative Architecture Engine v5.2</span>

          </motion.div>

          

          {/* Main Title Typography Scale */}

          <h1 style={{ margin: '0 0 24px 0', fontSize: '56px', fontWeight: 700, fontFamily: 'var(--font-display)', letterSpacing: '-0.02em', lineHeight: 1.15, color: '#FFFFFF' }}>

            BUILDWISE <span style={{ background: 'linear-gradient(135deg, #FFFFFF 40%, var(--gold-core) 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>AETHER</span>

          </h1>

          

          {/* Subtitle Minimal Elements */}

          <motion.p 

            initial={{ opacity: 0, y: 15 }}

            animate={{ opacity: 1, y: 0 }}

            transition={{ duration: 0.8, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}

            style={{ margin: '0 auto 48px auto', fontSize: '15px', color: 'var(--text-secondary)', lineHeight: '1.7', fontWeight: 400, maxWidth: '640px' }}

          >

            An autonomous architectural workspace calculation array that processes structural constraints, estimates building materials, and drafts coordinate vector blueprints instantly.

          </motion.p>

          

          <motion.div 

            initial={{ opacity: 0, y: 15 }}

            animate={{ opacity: 1, y: 0 }}

            transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}

          >

            <button 

              onClick={() => sectionRefs.input.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })}

              style={{ background: 'transparent', color: 'var(--gold-light)', border: '1px solid var(--border-gold)', padding: '14px 36px', borderRadius: '12px', fontSize: '12.2px', fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font-sans)', letterSpacing: '0.05em', transition: 'all 0.3s ease', backgroundColor: 'rgba(197, 168, 98, 0.02)' }}

              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--gold-core)'; e.currentTarget.style.backgroundColor = 'rgba(197, 168, 98, 0.06)'; }}

              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-gold)'; e.currentTarget.style.backgroundColor = 'rgba(197, 168, 98, 0.02)'; }}

            >

              Generating Blueprint...

            </button>

          </motion.div>

        </div>

      </section>



      {/* PRINCIPAL STUDIO WORKSPACE GRID BOUNDS */}

      <div className="studio-content-width" style={{ maxWidth: '1200px', paddingBottom: '120px' }}>

        

        {/* PREMIUM STRUCTURAL INPUT ELEMENT FORM */}

        <motion.fieldset 

          ref={sectionRefs.input}

          {...viewportFadeSlideInConfig}

          className="blueprint-card-slab"

        >

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px' }}>

            <span style={{ fontSize: '15px', color: 'var(--gold-core)' }}>📐</span>

            <legend style={{ padding: 0, fontSize: '22.5px', fontWeight: 600, fontFamily: 'var(--font-display)', color: '#FFFFFF', letterSpacing: '-0.01em' }}>Core Input Target Specifications</legend>

          </div>

          

          <p style={{ margin: '0 0 28px 0', fontSize: '13.2px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>

            Input natural language parameters. The structural synthesis model cross-references load calculations and traces room boundary vectors accordingly.

          </p>



          <div style={{ position: 'relative', marginBottom: '24px' }}>

            <textarea

              className="blueprint-textarea-terminal"

              value={inputText}

              onChange={(e) => setInputText(e.target.value)}

              placeholder="Ex: Provide structural mappings for a modern high-clearance design..."

            />

          </div>



          {errorBanner && (

            <motion.div 

              initial={{ opacity: 0, scale: 0.99 }}

              animate={{ opacity: 1, scale: 1 }}

              style={{ marginBottom: '24px', padding: '16px 20px', backgroundColor: 'rgba(239, 68, 68, 0.03)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '10px', fontSize: '12.2px', color: '#FCA5A5', fontFamily: 'var(--font-mono)', display: 'flex', gap: '12px', alignItems: 'center' }}

            >

              <span>⚠️</span>

              <span><strong>CALCULATION INTERRUPT:</strong> {errorBanner}</span>

            </motion.div>

          )}



          {/* Core Magnetic Execution Core Element */}

          <MagneticActionButton

            onClick={() => executeMatrixGeneration()}

            disabled={isProcessing}

            premiumClass="premium-execution-trigger"

          >

            <div style={{ 

              width: '100%', 

              height: '54px', 

              background: 'linear-gradient(135deg, #FFFFFF 0%, var(--gold-light) 50%, var(--gold-core) 100%)',

              color: '#08080A',

              fontSize: '12.2px',

              fontWeight: 700,

              fontFamily: 'var(--font-sans)',

              textTransform: 'uppercase',

              letterSpacing: '0.06em',

              border: 'none',

              borderRadius: '12px',

              cursor: isProcessing ? 'not-allowed' : 'pointer',

              display: 'flex',

              alignItems: 'center',

              justifyContent: 'center',

              gap: '10px',

              boxShadow: '0 8px 30px rgba(197, 168, 98, 0.15)'

            }}>

              {isProcessing ? "Processing Architectural Matrix Blocks..." : "Compile Layout Coordinates"}

            </div>

          </MagneticActionButton>

        </motion.fieldset>



        {/* COMPREHENSIVE ARCHITECTURAL LOADING SEQUENCE BANNER */}

        <AnimatePresence>

          {isProcessing && (

            <motion.div 

              initial={{ opacity: 0, y: 15, scale: 0.99 }}

              animate={{ opacity: 1, y: 0, scale: 1 }}

              exit={{ opacity: 0, y: -15, scale: 0.99 }}

              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}

              className="blueprint-card-slab"

              style={{ borderColor: 'var(--gold-core)', background: 'rgba(10, 10, 13, 0.95)' }}

            >

              <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>

                <motion.div 

                  animate={{ rotate: 360 }}

                  transition={{ repeat: Infinity, duration: 4, ease: "linear" }}

                  style={{ width: '40px', height: '40px', border: '1px dashed var(--gold-core)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '15px', flexShrink: 0 }}

                >

                  ⚙️

                </motion.div>

                <div style={{ flexGrow: 1 }}>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>

                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10.3px', color: 'var(--gold-light)', letterSpacing: '0.05em' }}>COMPUTATION RUNTIME LOGS</span>

                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10.3px', color: 'var(--text-muted)' }}>{matrixProgress}%</span>

                  </div>

                  <div className="blueprint-progress-track" style={{ marginBottom: '12px' }}>

                    <div className="blueprint-progress-bar" style={{ width: `${matrixProgress}%` }} />

                  </div>

                  <motion.div 

                    key={loadingStepText}

                    initial={{ opacity: 0, x: -4 }}

                    animate={{ opacity: 1, x: 0 }}

                    style={{ fontFamily: 'var(--font-mono)', fontSize: '12.2px', color: 'var(--text-main)' }}

                  >

                    &gt; {loadingStepText}

                  </motion.div>

                </div>

              </div>

            </motion.div>

          )}

        </AnimatePresence>



        {/* REFINEMENT PARAMETERS INPUT CLARIFICATION MATRIX */}

        <AnimatePresence>

          {backendPayload?.requires_clarification && (

            <motion.section

              initial={{ opacity: 0, y: 20 }}

              animate={{ opacity: 1, y: 0 }}

              className="blueprint-card-slab"

              style={{ borderLeft: '2px solid var(--gold-core)' }}

            >

              <h3 style={{ margin: '0 0 6px 0', fontSize: '12.2px', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--gold-core)', fontFamily: 'var(--font-mono)' }}>

                Missing Dimensions — Calibration Required

              </h3>

              <p style={{ margin: '0 0 24px 0', fontSize: '12.2px', color: 'var(--text-secondary)' }}>

                Answer each question below using quick-select or type a custom value, then click Submit.

              </p>



              <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>

                {(() => {

                  // Map backend field keys → quick-pick options

                  const QUICK_OPTIONS: Record<string, string[]> = {

                    plot_width:        ['20 ft', '25 ft', '30 ft', '40 ft', '50 ft', '60 ft'],

                    plot_depth:        ['30 ft', '40 ft', '50 ft', '60 ft', '80 ft', '100 ft'],

                    floors_requested:  ['1 floor', '2 floors', '3 floors', '4 floors'],

                    bhk_count:         ['1 BHK', '2 BHK', '3 BHK', '4 BHK', '5 BHK'],

                    road_direction:    ['North', 'South', 'East', 'West'],

                    interior_style:    ['Modern', 'Traditional', 'Minimalist', 'Contemporary', 'Luxe'],

                    parking_slots:     ['0', '1', '2', '3'],

                    paint_theme:       ['Modern', 'Universe theme', 'Natural theme', 'Ocean theme', 'Luxury', 'Pastel', 'Monochrome'],

                  };



                  const PLACEHOLDERS: Record<string, string> = {

                    plot_width:       'e.g. 30',

                    plot_depth:       'e.g. 40',

                    floors_requested: 'e.g. 2',

                    bhk_count:        'e.g. 3',

                    road_direction:   'e.g. North',

                    interior_style:   'e.g. Modern',

                    parking_slots:    'e.g. 1',

                    paint_theme:      "e.g. Universe theme, Natural theme, or any colours you'd like",

                  };



                  return backendPayload.missing_fields?.map((fieldKey: string, idx: number) => {

                    const questionText = backendPayload.questions?.[idx] || `Specify value for ${fieldKey.replace(/_/g, ' ')}:`;

                    const quickOpts = QUICK_OPTIONS[fieldKey] ?? [];

                    const placeholder = PLACEHOLDERS[fieldKey] ?? 'Type your answer…';

                    const currentTextVal = qaTextInputs[fieldKey] ?? '';

                    const alreadyAnswered = qaMemory[fieldKey];



                    return (

                      <div key={fieldKey}>

                        <p style={{ margin: '0 0 12px 0', fontSize: '13.5px', color: '#FFFFFF', fontWeight: 500, lineHeight: 1.5 }}>

                          {questionText}

                        </p>



                        {/* Quick-pick pills */}

                        {quickOpts.length > 0 && (

                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>

                            {quickOpts.map(opt => {

                              const isSelected = alreadyAnswered === opt || qaTextInputs[fieldKey] === opt;

                              return (

                                <button

                                  key={opt}

                                  onClick={() => setQaTextInputs(prev => ({ ...prev, [fieldKey]: opt }))}

                                  className="blueprint-interactive-pill"

                                  style={isSelected ? {

                                    backgroundColor: 'rgba(197, 168, 98, 0.18)',

                                    borderColor: 'var(--gold-core)',

                                    color: 'var(--gold-core)',

                                    fontWeight: 600,

                                  } : {}}

                                >

                                  {opt}

                                </button>

                              );

                            })}

                          </div>

                        )}



                        {/* Free-text input */}

                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>

                          <input

                            type="text"

                            value={currentTextVal}

                            placeholder={placeholder}

                            onChange={e => setQaTextInputs(prev => ({ ...prev, [fieldKey]: e.target.value }))}

                            onKeyDown={e => {

                              if (e.key === 'Enter' && currentTextVal.trim()) {

                                const updated = { ...qaMemory, [fieldKey]: currentTextVal.trim() };

                                setQaMemory(updated);

                                executeMatrixGeneration(updated);

                              }

                            }}

                            style={{

                              flex: 1,

                              background: 'rgba(255,255,255,0.03)',

                              border: '1px solid rgba(197, 168, 98, 0.25)',

                              borderRadius: '8px',

                              padding: '10px 14px',

                              fontSize: '13px',

                              color: '#FFFFFF',

                              fontFamily: 'var(--font-sans)',

                              outline: 'none',

                            }}

                          />

                          {alreadyAnswered && (

                            <span style={{ fontSize: '11px', color: 'var(--gold-core)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>

                              ✓ {alreadyAnswered}

                            </span>

                          )}

                        </div>

                      </div>

                    );

                  });

                })()}

              </div>



              {/* Submit all answers button */}

              <div style={{ marginTop: '28px', display: 'flex', justifyContent: 'flex-end' }}>

                <MagneticActionButton

                  onClick={() => {

                    const merged = { ...qaMemory, ...qaTextInputs };

                    const filled = Object.fromEntries(

                      Object.entries(merged).filter(([_, v]) => v && String(v).trim())

                    );

                    setQaMemory(filled);

                    executeMatrixGeneration(filled);

                  }}

                  disabled={isProcessing}

                  premiumClass="premium-execution-trigger"

                >

                  <div style={{

                    padding: '0 32px',

                    height: '46px',

                    background: 'linear-gradient(135deg, #FFFFFF 0%, var(--gold-light) 50%, var(--gold-core) 100%)',

                    color: '#08080A',

                    fontSize: '11.5px',

                    fontWeight: 700,

                    fontFamily: 'var(--font-sans)',

                    textTransform: 'uppercase',

                    letterSpacing: '0.06em',

                    border: 'none',

                    borderRadius: '10px',

                    cursor: isProcessing ? 'not-allowed' : 'pointer',

                    display: 'flex',

                    alignItems: 'center',

                    justifyContent: 'center',

                    gap: '8px',

                  }}>

                    {isProcessing ? 'Processing…' : '▶ Submit Answers & Generate'}

                  </div>

                </MagneticActionButton>

              </div>

            </motion.section>

          )}

        </AnimatePresence>



        {/* ======================================================================

            CONTINUOUS UNROLLED DESIGN LAYERS (ALPHA AND BETA SYSTEM SUITES)

           ====================================================================== */}

        

        {/* DESIGN SUITE OPTION ALPHA */}

        <div ref={sectionRefs.optionA} style={{ marginTop: '40px' }}>

          <div style={{ marginBottom: '32px', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '16px' }}>

            <span style={{ fontSize: '10.3px', fontWeight: 600, color: 'var(--gold-core)', letterSpacing: '0.15em', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>SCHEMATIC ARTIFACT MATRIX ALPHA</span>

            <h2 style={{ margin: '6px 0 0 0', fontSize: '34px', fontFamily: 'var(--font-display)', fontWeight: 600, color: '#FFFFFF' }}>

              {backendPayload?.options?.OPTION_A_SPACE?.title || "Option A: Volumetric Space Adaptive Layout"}

            </h2>

          </div>



          {/* UNROLLED SEGMENT LAYER 01: GROUND FLOORS */}

          <motion.div {...viewportFadeSlideInConfig} style={{ marginBottom: '40px' }}>

            <h3 style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--gold-light)', marginBottom: '14px' }}>01 / Ground Level Map Plan</h3>

            {backendPayload?.options?.OPTION_A_SPACE?.floors?.[0] ? (

              <div className="blueprint-card-slab" style={{ padding: '24px' }}>

                <CADBlueprint floorData={backendPayload.options.OPTION_A_SPACE.floors[0]} />

              </div>

            ) : (

              <div className="blueprint-placeholder-state">Ground level coordinate arrays empty. Execute compilation pass above.</div>

            )}

          </motion.div>



          {/* UNROLLED SEGMENT LAYER 02: FIRST FLOORS */}

          <motion.div {...viewportFadeSlideInConfig} style={{ marginBottom: '40px' }}>

            <h3 style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--gold-light)', marginBottom: '14px' }}>02 / First Level Map Plan</h3>

            {backendPayload?.options?.OPTION_A_SPACE?.floors?.[1] ? (

              <div className="blueprint-card-slab" style={{ padding: '24px' }}>

                <CADBlueprint floorData={backendPayload.options.OPTION_A_SPACE.floors[1]} />

              </div>

            ) : (

              <div className="blueprint-placeholder-state">First level coordinate arrays empty. Execute compilation pass above.</div>

            )}

          </motion.div>



          {/* UNROLLED SEGMENT LAYER 03: SECOND FLOORS */}

          <motion.div {...viewportFadeSlideInConfig} style={{ marginBottom: '40px' }}>

            <h3 style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--gold-light)', marginBottom: '14px' }}>03 / Second Level Map Plan</h3>

            {backendPayload?.options?.OPTION_A_SPACE?.floors?.[2] ? (

              <div className="blueprint-card-slab" style={{ padding: '24px' }}>

                <CADBlueprint floorData={backendPayload.options.OPTION_A_SPACE.floors[2]} />

              </div>

            ) : (

              <div className="blueprint-placeholder-state">Level index unallocated in prompt specification parameters matrix.</div>

            )}

          </motion.div>



          {/* LAYER REVIEWS EVALUATION BLOCK */}

          <motion.div {...viewportFadeSlideInConfig} className="blueprint-card-slab" style={{ marginTop: '24px' }}>

            <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 600, color: 'var(--gold-core)', display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)' }}>

              <span>👁️</span> Engineering Trace Evaluation Matrix

            </h4>

            <p style={{ margin: 0, fontSize: '13.2px', color: 'var(--text-secondary)', lineHeight: '1.7' }}>

              {backendPayload?.options?.OPTION_A_SPACE?.analysis || "System awaiting target layout evaluation values to resolve physical clearance metrics."}

            </p>

          </motion.div>

        </div>



        <div className="minimal-gold-divider" />



        {/* DESIGN SUITE OPTION BETA */}

        <div ref={sectionRefs.optionB}>

          <div style={{ marginBottom: '32px', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '16px' }}>

            <span style={{ fontSize: '10.3px', fontWeight: 600, color: 'var(--gold-light)', letterSpacing: '0.15em', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>SCHEMATIC ARTIFACT MATRIX BETA</span>

            <h2 style={{ margin: '6px 0 0 0', fontSize: '34px', fontFamily: 'var(--font-display)', fontWeight: 600, color: '#FFFFFF' }}>

              {backendPayload?.options?.OPTION_B_VASTU?.title || "Option B: Orientational Vastu Harmonic Layout"}

            </h2>

          </div>



          {/* UNROLLED SEGMENT LAYER 01: GROUND FLOORS */}

          <motion.div {...viewportFadeSlideInConfig} style={{ marginBottom: '40px' }}>

            <h3 style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--gold-light)', marginBottom: '14px' }}>01 / Ground Level Map Plan</h3>

            {backendPayload?.options?.OPTION_B_VASTU?.floors?.[0] ? (

              <div className="blueprint-card-slab" style={{ padding: '24px' }}>

                <CADBlueprint floorData={backendPayload.options.OPTION_B_VASTU.floors[0]} />

              </div>

            ) : (

              <div className="blueprint-placeholder-state">Ground level coordinate arrays empty. Execute compilation pass above.</div>

            )}

          </motion.div>



          {/* UNROLLED SEGMENT LAYER 02: FIRST FLOORS */}

          <motion.div {...viewportFadeSlideInConfig} style={{ marginBottom: '40px' }}>

            <h3 style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--gold-light)', marginBottom: '14px' }}>02 / First Level Map Plan</h3>

            {backendPayload?.options?.OPTION_B_VASTU?.floors?.[1] ? (

              <div className="blueprint-card-slab" style={{ padding: '24px' }}>

                <CADBlueprint floorData={backendPayload.options.OPTION_B_VASTU.floors[1]} />

              </div>

            ) : (

              <div className="blueprint-placeholder-state">First level coordinate arrays empty. Execute compilation pass above.</div>

            )}

          </motion.div>



          {/* UNROLLED SEGMENT LAYER 03: SECOND FLOORS */}

          <motion.div {...viewportFadeSlideInConfig} style={{ marginBottom: '40px' }}>

            <h3 style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-display)', color: 'var(--gold-light)', marginBottom: '14px' }}>03 / Second Level Map Plan</h3>

            {backendPayload?.options?.OPTION_B_VASTU?.floors?.[2] ? (

              <div className="blueprint-card-slab" style={{ padding: '24px' }}>

                <CADBlueprint floorData={backendPayload.options.OPTION_B_VASTU.floors[2]} />

              </div>

            ) : (

              <div className="blueprint-placeholder-state">Level index unallocated in prompt specification parameters matrix.</div>

            )}

          </motion.div>



          {/* LAYER REVIEWS EVALUATION BLOCK */}

          <motion.div {...viewportFadeSlideInConfig} className="blueprint-card-slab" style={{ marginTop: '24px' }}>

            <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 600, color: 'var(--gold-light)', display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)' }}>

              <span>☯️</span> Orientational Soundness Report Matrix

            </h4>

            <p style={{ margin: 0, fontSize: '13.2px', color: 'var(--text-secondary)', lineHeight: '1.7' }}>

              {backendPayload?.options?.OPTION_B_VASTU?.analysis || "System awaiting directional solar vectors to complete harmonic mapping equations."}

            </p>

          </motion.div>

        </div>



        <div className="minimal-gold-divider" />



        {/* COMPARATIVE STRUCTURAL PERFORMANCE FIELDSETS */}

        <motion.fieldset 

          ref={sectionRefs.comparison} 

          {...viewportFadeSlideInConfig}

          className="blueprint-card-slab"

        >

          <legend style={{ padding: '0 10px', fontSize: '18.8px', fontWeight: 600, fontFamily: 'var(--font-display)', color: '#FFFFFF', display: 'flex', alignItems: 'center', gap: '10px' }}>

            <span>🎛️</span> Comparative Clearance Matrix

          </legend>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '12px' }}>

            <div style={{ backgroundColor: 'rgba(8,8,10,0.4)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.02)' }}>

              <h5 style={{ margin: '0 0 12px 0', color: 'var(--gold-core)', fontSize: '13.2px', fontWeight: 600, fontFamily: 'var(--font-display)' }}>Alpha Plan Metrics</h5>

              <p style={{ margin: '0 0 8px 0', fontSize: '12.2px', color: 'var(--text-secondary)' }}>Space Net Yield Coefficient: <strong style={{ color: '#FFFFFF' }}>94% Efficiency Factor</strong></p>

              <p style={{ margin: '0 0 8px 0', fontSize: '12.2px', color: 'var(--text-secondary)' }}>Circulation Friction Index: <strong style={{ color: '#FFFFFF' }}>4% Total</strong></p>

              <p style={{ margin: 0, fontSize: '12.2px', color: 'var(--text-secondary)' }}>Vastu Adherence Score: <strong style={{ color: '#FFFFFF' }}>68 / 100 Limits</strong></p>

            </div>

            <div style={{ backgroundColor: 'rgba(8,8,10,0.4)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.02)' }}>

              <h5 style={{ margin: '0 0 12px 0', color: 'var(--gold-light)', fontSize: '13.2px', fontWeight: 600, fontFamily: 'var(--font-display)' }}>Beta Plan Metrics</h5>

              <p style={{ margin: '0 0 8px 0', fontSize: '12.2px', color: 'var(--text-secondary)' }}>Space Net Yield Coefficient: <strong style={{ color: '#FFFFFF' }}>89% Efficiency Factor</strong></p>

              <p style={{ margin: '0 0 8px 0', fontSize: '12.2px', color: 'var(--text-secondary)' }}>Circulation Friction Index: <strong style={{ color: '#FFFFFF' }}>8% Total</strong></p>

              <p style={{ margin: 0, fontSize: '12.2px', color: 'var(--text-secondary)' }}>Vastu Adherence Score: <strong style={{ color: '#FFFFFF' }}>95 / 100 Limits</strong></p>

            </div>

          </div>

        </motion.fieldset>



        {/* MATERIAL COST ESTIMATION SUMMARY SPREADSHEETS */}

        <motion.fieldset 

          ref={sectionRefs.cost} 

          {...viewportFadeSlideInConfig}

          className="blueprint-card-slab"

        >

          <legend style={{ padding: '0 10px', fontSize: '18.8px', fontWeight: 600, fontFamily: 'var(--font-display)', color: '#FFFFFF', display: 'flex', alignItems: 'center', gap: '10px' }}>

            <span>📊</span> Cost Valuation Spreadsheets

          </legend>

          <p style={{ margin: '4px 0 24px 0', fontSize: '13.2px', color: 'var(--text-secondary)' }}>

            Calculations verified using average global commodity indexes configured against high-grade rebar specifications.

          </p>

          

          {backendPayload?.options?.OPTION_A_SPACE?.cost_estimation ? (

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.7px' }}>

              <thead>

                <tr style={{ borderBottom: '1px solid rgba(197, 168, 98, 0.2)', textAlign: 'left', color: 'var(--text-muted)' }}>

                  <th style={{ paddingBottom: '12px', fontFamily: 'var(--font-mono)', fontSize: '10.3px', letterSpacing: '0.05em' }}>STRUCTURAL CALCULATED BLOCK</th>

                  <th style={{ paddingBottom: '12px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '10.3px', letterSpacing: '0.05em' }}>VALUATION METRIC (INR)</th>

                </tr>

              </thead>

              <tbody>

                {Object.entries(backendPayload.options.OPTION_A_SPACE.cost_estimation.breakdown || {}).map(([cKey, cVal]: [string, any], idx) => (

                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>

                    <td style={{ padding: '14px 0', color: 'var(--text-secondary)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', fontSize: '11.3px' }}>{cKey.replace(/_/g, ' ')}</td>

                    <td style={{ padding: '14px 0', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 500, color: '#FFFFFF' }}>

                      ₹<CoreNumericalCounter targetValue={cVal} />

                    </td>

                  </tr>

                ))}

                <tr style={{ fontWeight: 700, color: 'var(--gold-core)', fontSize: '14px' }}>

                  <td style={{ paddingTop: '24px', fontFamily: 'var(--font-display)' }}>TOTAL CONTRACTED STRUCTURAL ESTIMATE</td>

                  <td style={{ paddingTop: '24px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '15px' }}>

                    {backendPayload.options.OPTION_A_SPACE.cost_estimation.grand_total_inr}

                  </td>

                </tr>

              </tbody>

            </table>

          ) : (

            <div className="blueprint-placeholder-state" style={{ padding: '32px' }}>Awaiting active pipeline run coordinates to compute material ledger values.</div>

          )}

        </motion.fieldset>



        {/* CHROMATIC PAINT TREATMENT SEGMENTS */}

        <motion.fieldset 

          ref={sectionRefs.paint} 

          {...viewportFadeSlideInConfig}

          className="blueprint-card-slab"

        >

          <legend style={{ padding: '0 10px', fontSize: '18.8px', fontWeight: 600, fontFamily: 'var(--font-display)', color: '#FFFFFF', display: 'flex', alignItems: 'center', gap: '10px' }}>

            <span>🖌️</span> Chromatic Multiplier Index

          </legend>

          {(() => {

            // Pulled live from the backend's per-room paint_recommendations

            // (app/core/paint_engine.py), which is driven by whatever the

            // user actually typed -- prompt text, the paint_theme

            // clarification answer (e.g. "universe theme"), or interior_style.

            // This used to be a hardcoded 4-item array with fixed labels

            // ("Architectural Alabaster", "Slate Velvet", etc.) that never

            // read backendPayload at all, so no theme the user typed could

            // ever change what was shown here.

            const paintMap = backendPayload?.options?.OPTION_A_SPACE?.paint_recommendations;

            const entries: [string, any][] = paintMap ? Object.entries(paintMap) : [];



            if (entries.length === 0) {

              return (

                <div className="blueprint-placeholder-state" style={{ padding: '32px', marginTop: '12px' }}>

                  Awaiting active pipeline run coordinates to compute chromatic palette values.

                </div>

              );

            }



            const detectedTheme = entries[0][1]?.theme_detected;



            return (

              <>

                {detectedTheme && (

                  <p style={{ margin: '12px 0 16px 0', fontSize: '11.5px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>

                    DETECTED THEME: <span style={{ color: 'var(--gold-core)', fontWeight: 600 }}>{String(detectedTheme).toUpperCase()}</span>

                  </p>

                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: detectedTheme ? 0 : '12px' }}>

                  {entries.map(([roomName, rec], idx) => (

                    <div key={idx} style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', padding: '16px', backgroundColor: 'rgba(8,8,10,0.3)', border: '1px solid rgba(255,255,255,0.01)', borderRadius: '12px' }}>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexShrink: 0 }}>

                        <div

                          style={{ width: '24px', height: '24px', backgroundColor: rec?.primary?.hex || '#888', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)' }}

                          title={rec?.primary?.name}

                        />

                        <div

                          style={{ width: '24px', height: '24px', backgroundColor: rec?.accent?.hex || '#444', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)' }}

                          title={rec?.accent?.name}

                        />

                      </div>

                      <div>

                        <h6 style={{ margin: '0 0 4px 0', fontSize: '13.2px', fontWeight: 600, color: '#FFFFFF' }}>

                          {roomName} — {rec?.primary?.name}{rec?.accent?.name ? ` / ${rec.accent.name}` : ''}

                        </h6>

                        <p style={{ margin: 0, fontSize: '11.3px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>

                          {rec?.rationale || `${rec?.finish || 'standard'} finish, ${rec?.washable ? 'washable' : 'standard'} coating.`}

                        </p>

                      </div>

                    </div>

                  ))}

                </div>

              </>

            );

          })()}

        </motion.fieldset>



        {/* VECTOR BLUEPRINT PRINT EXPORT CHANNEL */}

        <div ref={sectionRefs.download} style={{ textAlign: 'center', marginTop: '64px' }}>

          <h4 style={{ margin: '0 0 6px 0', fontSize: '17px', fontWeight: 600, fontFamily: 'var(--font-display)', color: '#FFFFFF' }}>Export Document Vector Matrix</h4>

          <p style={{ margin: '0 0 24px 0', fontSize: '12.7px', color: 'var(--text-secondary)' }}>

            Package coordinate mapping lines into high-contrast print-ready documents.

          </p>

          <button

            onClick={() => window.print()}

            style={{ background: 'transparent', color: 'var(--gold-core)', border: '1px solid var(--border-gold)', padding: '12px 32px', borderRadius: '10px', fontSize: '12.2px', fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font-sans)', letterSpacing: '0.04em', transition: 'all 0.2s ease' }}

            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(197, 168, 98, 0.05)'; }}

            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}

          >

            📥 Print Output Sheets File

          </button>

        </div>



      </div>

    </motion.div>

  );

}