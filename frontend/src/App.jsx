import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Simple 3D Molecule Component
const MoleculeViewer = ({ drugName, isActive }) => {
  const canvasRef = useRef(null);
  
  useEffect(() => {
    if (!canvasRef.current || !isActive) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animationFrame;
    let rotation = 0;
    
    // Simple molecule structure (atoms and bonds)
    const atoms = [
      { x: 0, y: 0, z: 0, size: 20, color: '#3b82f6' },
      { x: 40, y: 20, z: 10, size: 15, color: '#ef4444' },
      { x: -30, y: 25, z: -15, size: 18, color: '#10b981' },
      { x: 20, y: -35, z: 20, size: 16, color: '#f59e0b' },
      { x: -25, y: -20, z: -10, size: 14, color: '#8b5cf6' },
    ];
    
    const bonds = [
      [0, 1], [0, 2], [0, 3], [0, 4], [1, 2], [3, 4]
    ];
    
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      rotation += 0.02;
      
      // Rotate and project 3D to 2D
      const rotatedAtoms = atoms.map(atom => {
        const x = atom.x * Math.cos(rotation) - atom.z * Math.sin(rotation);
        const z = atom.x * Math.sin(rotation) + atom.z * Math.cos(rotation);
        const y = atom.y * Math.cos(rotation * 0.7) - z * Math.sin(rotation * 0.7);
        const z2 = atom.y * Math.sin(rotation * 0.7) + z * Math.cos(rotation * 0.7);
        
        // Perspective projection
        const scale = 200 / (200 + z2);
        return {
          ...atom,
          screenX: canvas.width / 2 + x * scale,
          screenY: canvas.height / 2 + y * scale,
          scale: scale
        };
      });
      
      // Draw bonds
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 2;
      bonds.forEach(([i, j]) => {
        ctx.beginPath();
        ctx.moveTo(rotatedAtoms[i].screenX, rotatedAtoms[i].screenY);
        ctx.lineTo(rotatedAtoms[j].screenX, rotatedAtoms[j].screenY);
        ctx.stroke();
      });
      
      // Draw atoms
      rotatedAtoms.sort((a, b) => a.scale - b.scale).forEach(atom => {
        const gradient = ctx.createRadialGradient(
          atom.screenX, atom.screenY, 0,
          atom.screenX, atom.screenY, atom.size * atom.scale
        );
        gradient.addColorStop(0, atom.color);
        gradient.addColorStop(1, atom.color + '40');
        
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(atom.screenX, atom.screenY, atom.size * atom.scale, 0, Math.PI * 2);
        ctx.fill();
        
        // Shine effect
        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.beginPath();
        ctx.arc(
          atom.screenX - atom.size * atom.scale * 0.3,
          atom.screenY - atom.size * atom.scale * 0.3,
          atom.size * atom.scale * 0.4,
          0, Math.PI * 2
        );
        ctx.fill();
      });
      
      animationFrame = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => cancelAnimationFrame(animationFrame);
  }, [isActive]);
  
  return (
    <canvas 
      ref={canvasRef} 
      width={300} 
      height={300}
      className="rounded-lg"
      style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
    />
  );
};

// Particle Background Component
const ParticleBackground = () => {
  const canvasRef = useRef(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    
    const particles = Array.from({ length: 50 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      size: Math.random() * 3 + 1
    }));
    
    let animationFrame;
    const animate = () => {
      ctx.fillStyle = 'rgba(248, 250, 252, 0.05)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        
        // Draw particle
        ctx.fillStyle = 'rgba(99, 102, 241, 0.3)';
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
        
        // Draw connections
        particles.slice(i + 1).forEach(p2 => {
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < 150) {
            ctx.strokeStyle = `rgba(99, 102, 241, ${0.2 * (1 - dist / 150)})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        });
      });
      
      animationFrame = requestAnimationFrame(animate);
    };
    
    animate();
    
    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    
    window.addEventListener('resize', handleResize);
    
    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', handleResize);
    };
  }, []);
  
  return <canvas ref={canvasRef} className="fixed top-0 left-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }} />;
};

function App() {
  const [diseaseName, setDiseaseName] = useState('');
  const [topK, setTopK] = useState(10);
  const [minScore, setMinScore] = useState(0.3);
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [streamingStatus, setStreamingStatus] = useState('');
  const [selectedDrug, setSelectedDrug] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults(null);
    setStreamingStatus('Starting analysis...');

    try {
      const response = await fetch('http://localhost:8000/api/repurpose/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          disease_name: diseaseName,
          top_k: topK,
          min_score: minScore,
          anthropic_api_key: apiKey || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.stage === 'fetching') {
              setStreamingStatus(data.message);
            } else if (data.stage === 'disease_found') {
              setStreamingStatus(`Found: ${data.data.name} (${data.data.gene_count} genes, ${data.data.pathway_count} pathways)`);
            } else if (data.stage === 'graph_building') {
              setStreamingStatus(data.message);
            } else if (data.stage === 'graph_built') {
              setStreamingStatus(`Graph built: ${data.data.total_nodes} nodes, ${data.data.total_edges} edges`);
            } else if (data.stage === 'scoring') {
              setStreamingStatus(data.message);
            } else if (data.stage === 'scored') {
              setStreamingStatus(data.message);
            } else if (data.stage === 'explaining') {
              setStreamingStatus(data.message);
            } else if (data.stage === 'complete') {
              setResults(data.data);
              setStreamingStatus('Analysis complete!');
            } else if (data.stage === 'error') {
              setError(data.message);
              setStreamingStatus('');
            }
          }
        }
      }
    } catch (err) {
      setError(err.message);
      setStreamingStatus('');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 0.7) return '#10b981';
    if (score >= 0.5) return '#f59e0b';
    return '#ef4444';
  };

  const getConfidenceBadge = (confidence) => {
    const colors = {
      High: 'bg-green-100 text-green-800',
      Medium: 'bg-yellow-100 text-yellow-800',
      Low: 'bg-red-100 text-red-800',
    };
    return colors[confidence] || colors.Low;
  };

  return (
    <div className="min-h-screen relative overflow-hidden">
      <ParticleBackground />
      
      <div className="relative z-10 container mx-auto px-4 py-8 max-w-7xl">
        {/* Futuristic Header */}
        <div className="text-center mb-12 relative">
          <div className="absolute inset-0 flex items-center justify-center opacity-20">
            <div className="w-96 h-96 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full filter blur-3xl animate-pulse"></div>
          </div>
          <h1 className="text-6xl font-black mb-4 relative">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 animate-gradient">
              🧬 AI Drug Repurposing Engine
            </span>
          </h1>
          <p className="text-gray-600 text-xl font-light tracking-wide">
            Discover FDA-approved drugs for new therapeutic applications
          </p>
          <div className="mt-4 flex items-center justify-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-ping"></div>
            <span className="text-sm text-gray-500">Powered by AI & Knowledge Graphs</span>
          </div>
        </div>

        {/* Glassmorphism Input Form */}
        <div className="backdrop-blur-xl bg-white/40 rounded-3xl shadow-2xl p-8 mb-8 border border-white/50">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                🔬 Disease Name
              </label>
              <input
                type="text"
                value={diseaseName}
                onChange={(e) => setDiseaseName(e.target.value)}
                placeholder="e.g., Parkinson's Disease, Alzheimer's, Breast Cancer"
                className="w-full px-6 py-4 bg-white/60 border-2 border-purple-200 rounded-2xl focus:border-purple-500 focus:ring-4 focus:ring-purple-200/50 transition-all outline-none text-lg backdrop-blur-sm"
                required
              />
              <p className="mt-2 text-sm text-gray-600 flex items-center gap-2">
                <span className="text-purple-500">💡</span>
                Try: Parkinson, Alzheimer, ALS, Lupus, Crohn, Multiple Sclerosis
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                  📊 Number of Candidates
                </label>
                <input
                  type="number"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  min="1"
                  max="20"
                  className="w-full px-6 py-4 bg-white/60 border-2 border-blue-200 rounded-2xl focus:border-blue-500 focus:ring-4 focus:ring-blue-200/50 transition-all outline-none backdrop-blur-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                  🎯 Minimum Score
                </label>
                <input
                  type="number"
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                  min="0"
                  max="1"
                  step="0.1"
                  className="w-full px-6 py-4 bg-white/60 border-2 border-green-200 rounded-2xl focus:border-green-500 focus:ring-4 focus:ring-green-200/50 transition-all outline-none backdrop-blur-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                🔑 OpenAI API Key (Optional - for AI explanations)
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-proj-... or sk-..."
                className="w-full px-6 py-4 bg-white/60 border-2 border-pink-200 rounded-2xl focus:border-pink-500 focus:ring-4 focus:ring-pink-200/50 transition-all outline-none backdrop-blur-sm"
              />
              <p className="mt-2 text-sm text-gray-600 flex items-center gap-2">
                <span className="text-pink-500">✨</span>
                Optional: Get your free API key from platform.openai.com ($5 free credits)
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 text-white py-5 px-8 rounded-2xl font-bold text-xl hover:shadow-2xl hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none transition-all duration-300 relative overflow-hidden group"
            >
              <span className="relative z-10">{loading ? '⚡ Analyzing...' : '🚀 Find Repurposing Candidates'}</span>
              <div className="absolute inset-0 bg-gradient-to-r from-pink-600 via-purple-600 to-blue-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            </button>
          </form>

          {/* Animated Streaming Status */}
          {streamingStatus && (
            <div className="mt-6 p-5 bg-gradient-to-r from-blue-50 to-purple-50 border-l-4 border-blue-500 rounded-xl backdrop-blur-sm animate-fade-in">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse"></div>
                <p className="text-blue-700 font-semibold">{streamingStatus}</p>
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="mt-6 p-5 bg-red-50 border-l-4 border-red-500 rounded-xl animate-shake">
              <p className="text-red-700 font-semibold">❌ Error: {error}</p>
            </div>
          )}
        </div>

        {/* Results */}
        {results && (
          <div className="space-y-8 animate-fade-in">
            {/* Disease Info Card */}
            <div className="backdrop-blur-xl bg-white/40 rounded-3xl shadow-2xl p-8 border border-white/50">
              <h2 className="text-4xl font-black text-gray-800 mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
                {results.disease_name}
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className="bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl p-6 text-white shadow-lg transform hover:scale-105 transition-transform">
                  <p className="text-sm opacity-90 mb-2">Associated Genes</p>
                  <p className="text-4xl font-black">{results.disease_genes.length}</p>
                </div>
                <div className="bg-gradient-to-br from-purple-400 to-purple-600 rounded-2xl p-6 text-white shadow-lg transform hover:scale-105 transition-transform">
                  <p className="text-sm opacity-90 mb-2">Pathways</p>
                  <p className="text-4xl font-black">{results.disease_pathways.length}</p>
                </div>
                <div className="bg-gradient-to-br from-green-400 to-green-600 rounded-2xl p-6 text-white shadow-lg transform hover:scale-105 transition-transform">
                  <p className="text-sm opacity-90 mb-2">Candidates Found</p>
                  <p className="text-4xl font-black">{results.candidates.length}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-bold text-gray-800 mb-3 text-lg">🧬 Top Genes</h3>
                  <div className="flex flex-wrap gap-2">
                    {results.disease_genes.slice(0, 10).map((gene, i) => (
                      <span key={gene} className="px-4 py-2 bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 rounded-full text-sm font-semibold shadow-sm hover:shadow-md transition-shadow" style={{ animationDelay: `${i * 0.1}s` }}>
                        {gene}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="font-bold text-gray-800 mb-3 text-lg">🔬 Key Pathways</h3>
                  <div className="flex flex-wrap gap-2">
                    {results.disease_pathways.slice(0, 5).map((pathway, i) => (
                      <span key={pathway} className="px-4 py-2 bg-gradient-to-r from-purple-100 to-purple-200 text-purple-800 rounded-full text-sm font-semibold shadow-sm hover:shadow-md transition-shadow" style={{ animationDelay: `${i * 0.1}s` }}>
                        {pathway}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Drug Candidates */}
            <div>
              <h2 className="text-4xl font-black text-gray-800 mb-6 bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-600">
                💊 Drug Repurposing Candidates
              </h2>
              <div className="space-y-6">
                {results.candidates.map((candidate, idx) => (
                  <div
                    key={candidate.drug_id}
                    className="backdrop-blur-xl bg-white/40 rounded-3xl shadow-xl hover:shadow-2xl transition-all duration-300 p-6 border border-white/50 transform hover:scale-[1.02] relative overflow-hidden group"
                    onClick={() => setSelectedDrug(selectedDrug === idx ? null : idx)}
                  >
                    {/* Background gradient effect */}
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                    
                    <div className="relative z-10">
                      <div className="flex flex-col md:flex-row gap-6">
                        {/* 3D Molecule Viewer */}
                        <div className="flex-shrink-0">
                          <MoleculeViewer drugName={candidate.drug_name} isActive={selectedDrug === idx} />
                        </div>
                        
                        {/* Drug Info */}
                        <div className="flex-grow">
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex-grow">
                              <div className="flex items-center gap-3 mb-2 flex-wrap">
                                <h3 className="text-3xl font-black text-gray-800">
                                  #{idx + 1}. {candidate.drug_name}
                                </h3>
                                <span className={`px-4 py-1 rounded-full text-sm font-bold ${getConfidenceBadge(candidate.confidence)} shadow-sm`}>
                                  {candidate.confidence} Confidence
                                </span>
                              </div>
                              <p className="text-gray-600 font-medium">
                                <span className="text-purple-600">💼 Current Use:</span> {candidate.original_indication}
                              </p>
                            </div>
                            <div className="text-right ml-4">
                              <p className="text-sm text-gray-600 mb-1 font-semibold">Score</p>
                              <div className="relative">
                                <p
                                  className="text-5xl font-black drop-shadow-lg"
                                  style={{ color: getScoreColor(candidate.composite_score) }}
                                >
                                  {(candidate.composite_score * 100).toFixed(0)}
                                </p>
                                <span className="text-2xl font-bold text-gray-400">%</span>
                              </div>
                            </div>
                          </div>

                          <div className="mb-4">
                            <p className="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                              ⚙️ Mechanism of Action
                            </p>
                            <p className="text-gray-700 bg-gradient-to-r from-gray-50 to-gray-100 p-4 rounded-xl font-medium border border-gray-200">{candidate.mechanism}</p>
                          </div>

                          {candidate.explanation && (
                            <div className="mb-4">
                              <p className="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                                🎯 Why This Might Work
                              </p>
                              <p className="text-gray-700 bg-gradient-to-r from-blue-50 to-purple-50 p-4 rounded-xl leading-relaxed font-medium border border-blue-200">
                                {candidate.explanation}
                              </p>
                            </div>
                          )}

                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                            <div className="bg-gradient-to-br from-blue-100 to-blue-200 rounded-xl p-4 text-center">
                              <p className="text-xs text-blue-900 mb-1 font-bold">Gene Targeting</p>
                              <p className="text-2xl font-black text-blue-900">
                                {(candidate.gene_target_score * 100).toFixed(0)}%
                              </p>
                            </div>
                            <div className="bg-gradient-to-br from-purple-100 to-purple-200 rounded-xl p-4 text-center">
                              <p className="text-xs text-purple-900 mb-1 font-bold">Pathway Overlap</p>
                              <p className="text-2xl font-black text-purple-900">
                                {(candidate.pathway_overlap_score * 100).toFixed(0)}%
                              </p>
                            </div>
                            <div className="bg-gradient-to-br from-green-100 to-green-200 rounded-xl p-4 text-center">
                              <p className="text-xs text-green-900 mb-1 font-bold">Shared Genes</p>
                              <p className="text-2xl font-black text-green-900">{candidate.shared_genes.length}</p>
                            </div>
                            <div className="bg-gradient-to-br from-pink-100 to-pink-200 rounded-xl p-4 text-center">
                              <p className="text-xs text-pink-900 mb-1 font-bold">Shared Pathways</p>
                              <p className="text-2xl font-black text-pink-900">{candidate.shared_pathways.length}</p>
                            </div>
                          </div>

                          {candidate.shared_genes.length > 0 && (
                            <div className="mb-3">
                              <p className="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                                🎯 Shared Target Genes
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {candidate.shared_genes.map((gene) => (
                                  <span key={gene} className="px-3 py-1 bg-gradient-to-r from-green-100 to-emerald-200 text-green-900 rounded-lg text-xs font-bold shadow-sm">
                                    {gene}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {candidate.shared_pathways.length > 0 && (
                            <div>
                              <p className="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                                🔬 Shared Pathways
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {candidate.shared_pathways.map((pathway) => (
                                  <span key={pathway} className="px-3 py-1 bg-gradient-to-r from-purple-100 to-violet-200 text-purple-900 rounded-lg text-xs font-bold shadow-sm">
                                    {pathway}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Graph Stats */}
            {results.graph_stats && (
              <div className="backdrop-blur-xl bg-white/40 rounded-3xl shadow-2xl p-8 border border-white/50">
                <h3 className="text-3xl font-black text-gray-800 mb-6 bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
                  📊 Knowledge Graph Statistics
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl p-6 text-white shadow-lg">
                    <p className="text-5xl font-black mb-2">{results.graph_stats.total_nodes}</p>
                    <p className="text-sm opacity-90 font-semibold">Total Nodes</p>
                  </div>
                  <div className="text-center bg-gradient-to-br from-purple-400 to-purple-600 rounded-2xl p-6 text-white shadow-lg">
                    <p className="text-5xl font-black mb-2">{results.graph_stats.total_edges}</p>
                    <p className="text-sm opacity-90 font-semibold">Total Edges</p>
                  </div>
                  <div className="text-center bg-gradient-to-br from-green-400 to-green-600 rounded-2xl p-6 text-white shadow-lg">
                    <p className="text-5xl font-black mb-2">
                      {results.graph_stats.node_types?.gene || 0}
                    </p>
                    <p className="text-sm opacity-90 font-semibold">Gene Nodes</p>
                  </div>
                  <div className="text-center bg-gradient-to-br from-orange-400 to-orange-600 rounded-2xl p-6 text-white shadow-lg">
                    <p className="text-5xl font-black mb-2">
                      {results.graph_stats.node_types?.drug || 0}
                    </p>
                    <p className="text-sm opacity-90 font-semibold">Drug Nodes</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      
      <style jsx>{`
        @keyframes gradient {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        .animate-gradient {
          background-size: 200% 200%;
          animation: gradient 3s ease infinite;
        }
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.5s ease-out;
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
          20%, 40%, 60%, 80% { transform: translateX(5px); }
        }
        .animate-shake {
          animation: shake 0.5s;
        }
      `}</style>
    </div>
  );
}

export default App;