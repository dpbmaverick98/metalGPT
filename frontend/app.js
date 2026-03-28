/**
 * MetalGPT Frontend Application
 * Handles 3D viewer, chat interface, and backend communication
 */

class MetalGPTApp {
    constructor() {
        this.sessionId = null;
        this.ws = null;
        this.apiUrl = 'http://localhost:8000';
        this.wsUrl = 'ws://localhost:8000/ws/chat';
        
        this.viewer = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        
        this.castGeometry = null;
        this.risers = [];
        this.simulationResults = null;
        
        this.init();
    }
    
    init() {
        this.initViewer();
        this.initWebSocket();
        this.initDragDrop();
        this.initFileInput();
    }
    
    // ==================== 3D VIEWER ====================
    
    initViewer() {
        const canvas = document.getElementById('canvas3d');
        
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0f0f1a);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(
            45, canvas.clientWidth / canvas.clientHeight, 0.1, 10000
        );
        this.camera.position.set(200, 200, 200);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
        this.renderer.shadowMap.enabled = true;
        
        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(100, 200, 100);
        directionalLight.castShadow = true;
        this.scene.add(directionalLight);
        
        const pointLight = new THREE.PointLight(0x00d4ff, 0.5);
        pointLight.position.set(-100, 100, -100);
        this.scene.add(pointLight);
        
        // Grid
        const gridHelper = new THREE.GridHelper(500, 50, 0x333355, 0x222233);
        this.scene.add(gridHelper);
        
        // Axes
        const axesHelper = new THREE.AxesHelper(100);
        this.scene.add(axesHelper);
        
        // Animation loop
        this.animate();
        
        // Handle resize
        window.addEventListener('resize', () => this.onResize());
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
    
    onResize() {
        const canvas = document.getElementById('canvas3d');
        const container = canvas.parentElement;
        
        this.camera.aspect = container.clientWidth / container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(container.clientWidth, container.clientHeight);
    }
    
    // ==================== WEBSOCKET ====================
    
    initWebSocket() {
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            setTimeout(() => this.initWebSocket(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleWebSocketMessage(data) {
        if (data.type === 'response') {
            this.hideTyping();
            this.addMessage(data.text, 'ai');
            
            if (data.actions) {
                this.addActionButtons(data.actions);
            }
            
            if (data.data) {
                this.updateVisualization(data.data);
            }
        } else if (data.type === 'progress') {
            this.updateProgress(data.data);
        }
    }
    
    // ==================== CHAT INTERFACE ====================
    
    addMessage(text, sender) {
        const container = document.getElementById('chatMessages');
        const message = document.createElement('div');
        message.className = `message ${sender}`;
        message.innerHTML = text;
        container.appendChild(message);
        container.scrollTop = container.scrollHeight;
    }
    
    showTyping() {
        document.getElementById('typingIndicator').classList.add('active');
        const container = document.getElementById('chatMessages');
        container.scrollTop = container.scrollHeight;
    }
    
    hideTyping() {
        document.getElementById('typingIndicator').classList.remove('active');
    }
    
    addActionButtons(actions) {
        const container = document.getElementById('chatMessages');
        const lastMessage = container.lastElementChild;
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'message-actions';
        
        actions.forEach(action => {
            const btn = document.createElement('button');
            btn.className = 'btn';
            btn.textContent = action.label;
            btn.onclick = () => this.handleAction(action);
            actionsDiv.appendChild(btn);
        });
        
        lastMessage.appendChild(actionsDiv);
    }
    
    handleAction(action) {
        if (action.type === 'start_optimization') {
            this.optimize(action.material);
        } else if (action.type === 'start_improvement_loop') {
            this.runImprovementLoop(action.material);
        } else if (action.type === 'start_simulation') {
            this.simulate();
        } else if (action.action === 'optimize') {
            this.optimize();
        } else if (action.action === 'improve') {
            this.runImprovementLoop();
        } else if (action.action === 'simulate') {
            this.simulate();
        } else if (action.action === 'analyze') {
            this.analyze();
        } else if (action.action === 'view_3d') {
            this.showSimulationResults();
        }
    }
    
    sendMessage() {
        const input = document.getElementById('chatInput');
        const text = input.value.trim();
        
        if (!text) return;
        
        this.addMessage(text, 'user');
        input.value = '';
        
        this.showTyping();
        
        // Send via WebSocket
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                text: text,
                session_id: this.sessionId
            }));
        } else {
            // Fallback to HTTP
            this.sendHttpMessage(text);
        }
    }
    
    async sendHttpMessage(text) {
        try {
            const response = await fetch(`${this.apiUrl}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    session_id: this.sessionId
                })
            });
            
            const data = await response.json();
            this.hideTyping();
            this.addMessage(data.text, 'ai');
            
            if (data.actions) {
                this.addActionButtons(data.actions);
            }
        } catch (error) {
            this.hideTyping();
            this.addMessage('Sorry, I encountered an error. Please try again.', 'ai');
            console.error(error);
        }
    }
    
    quickCommand(text) {
        document.getElementById('chatInput').value = text;
        this.sendMessage();
    }
    
    // ==================== FILE UPLOAD ====================
    
    initDragDrop() {
        const dropZone = document.getElementById('dropZone');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('drag-over');
            });
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('drag-over');
            });
        });
        
        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.processFile(files[0]);
            }
        });
    }
    
    initFileInput() {
        const input = document.getElementById('fileInput');
        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.processFile(e.target.files[0]);
            }
        });
    }
    
    uploadFile() {
        document.getElementById('fileInput').click();
    }
    
    async processFile(file) {
        this.showProgress('Uploading and processing...', 10);
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch(`${this.apiUrl}/api/upload`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                this.hideDropZone();
                this.showStatsOverlay();
                this.updateStats(data.geometry);
                this.addMessage(data.message, 'ai');
                this.createPlaceholderGeometry();
            } else {
                this.addMessage(`Error: ${data.error}`, 'ai');
            }
        } catch (error) {
            this.addMessage('Upload failed. Please try again.', 'ai');
            console.error(error);
        }
        
        this.hideProgress();
    }
    
    // ==================== API ACTIONS ====================
    
    async analyze() {
        if (!this.sessionId) {
            this.addMessage('Please upload a casting model first.', 'ai');
            return;
        }
        
        this.showTyping();
        
        try {
            const response = await fetch(`${this.apiUrl}/api/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            });
            
            const data = await response.json();
            this.hideTyping();
            
            let message = `📊 **Analysis Results**\n\n`;
            message += `**Hot Spots:** ${data.hotspots.length}\n`;
            message += `**Feeding Zones:** ${data.feeding_zones.length}\n\n`;
            
            if (data.recommendations) {
                message += data.recommendations.join('\n');
            }
            
            this.addMessage(message, 'ai');
            this.visualizeHotspots(data.hotspots);
            
        } catch (error) {
            this.hideTyping();
            this.addMessage('Analysis failed. Please try again.', 'ai');
        }
    }
    
    async optimize(material = 'aluminum_a356') {
        if (!this.sessionId) {
            this.addMessage('Please upload a casting model first.', 'ai');
            return;
        }
        
        this.showProgress('Optimizing casting design...', 0);
        this.addMessage('🔧 Running AI optimization...', 'ai');
        
        try {
            const response = await fetch(`${this.apiUrl}/api/optimize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    material: material
                })
            });
            
            const data = await response.json();
            this.hideProgress();
            
            if (data.success) {
                this.risers = data.risers;
                this.updateStats({ risers: data.risers.length, yield: data.yield });
                this.addMessage(data.message, 'ai');
                this.visualizeRisers(data.risers);
            } else {
                this.addMessage(`Optimization failed: ${data.error}`, 'ai');
            }
        } catch (error) {
            this.hideProgress();
            this.addMessage('Optimization failed. Please try again.', 'ai');
        }
    }
    
    async simulate() {
        if (!this.sessionId) {
            this.addMessage('Please upload a casting model first.', 'ai');
            return;
        }
        
        this.showProgress('Running solidification simulation...', 0);
        this.addMessage('🔥 Simulating solidification...', 'ai');
        
        try {
            const response = await fetch(`${this.apiUrl}/api/simulate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            });
            
            const data = await response.json();
            this.hideProgress();
            
            if (data.success) {
                this.simulationResults = data;
                
                let message = `📈 **Simulation Complete**\n\n`;
                message += `**Solidification Time:** ${data.solidification_time.toFixed(1)}s\n`;
                message += `**Defects Found:** ${data.defects.length}\n\n`;
                
                if (data.defects.length > 0) {
                    message += '**Defects:**\n';
                    data.defects.slice(0, 3).forEach(d => {
                        message += `- ${d.type.replace(/_/g, ' ')} (${d.severity})\n`;
                    });
                    message += '\nWould you like me to run the improvement loop?';
                    
                    this.addMessage(message, 'ai');
                    this.addActionButtons([
                        { type: 'button', label: '🔁 Auto-Fix Defects', action: 'improve' },
                        { type: 'button', label: 'Manual Re-optimize', action: 'optimize' }
                    ]);
                } else {
                    message += '✅ No defects predicted!';
                    this.addMessage(message, 'ai');
                }
                
                this.visualizeDefects(data.defects);
            } else {
                this.addMessage(`Simulation failed: ${data.error}`, 'ai');
            }
        } catch (error) {
            this.hideProgress();
            this.addMessage('Simulation failed. Please try again.', 'ai');
        }
    }
    
    async runImprovementLoop(material = 'aluminum_a356') {
        if (!this.sessionId) {
            this.addMessage('Please upload a casting model first.', 'ai');
            return;
        }
        
        this.showProgress('🔄 Starting AI Improvement Loop...', 0);
        this.addMessage('🔄 Running AI Improvement Loop...\n\nThis will automatically optimize until defects are eliminated.', 'ai');
        
        try {
            const response = await fetch(`${this.apiUrl}/api/improve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    material: material,
                    max_iterations: 10
                })
            });
            
            const data = await response.json();
            this.hideProgress();
            
            if (data.success) {
                this.risers = data.risers;
                this.simulationResults = data.final_simulation;
                this.updateStats({ 
                    risers: data.risers.length, 
                    yield: data.final_yield,
                    defects: data.final_defects 
                });
                
                // Build detailed message
                let message = `✅ **Improvement Loop Complete**\n\n`;
                message += `**Iterations:** ${data.iterations}\n`;
                message += `**Final Defects:** ${data.final_defects}\n`;
                message += `**Final Yield:** ${data.final_yield.toFixed(1f)}%\n\n`;
                
                if (data.converged) {
                    message += '🎉 **Defect-free design achieved!**\n\n';
                } else {
                    message += '⚠️ Some defects remain after max iterations.\n\n';
                }
                
                message += '**Iteration History:**\n';
                data.iteration_history.forEach(ih => {
                    message += `  Iter ${ih.iteration}: ${ih.defect_count} defects, ${ih.yield.toFixed(1)}% yield\n`;
                });
                
                this.addMessage(message, 'ai');
                this.visualizeRisers(data.risers);
                
                if (data.final_defects > 0) {
                    this.visualizeDefects(data.final_simulation.defects);
                }
            } else {
                this.addMessage(`Improvement loop failed: ${data.error}`, 'ai');
            }
        } catch (error) {
            this.hideProgress();
            this.addMessage('Improvement loop failed. Please try again.', 'ai');
            console.error(error);
        }
    }
    
    // ==================== VISUALIZATION ====================
    
    createPlaceholderGeometry() {
        // Create a placeholder cube representing the casting
        const geometry = new THREE.BoxGeometry(100, 60, 80);
        const material = new THREE.MeshPhongMaterial({
            color: 0x888899,
            transparent: true,
            opacity: 0.8
        });
        
        this.castGeometry = new THREE.Mesh(geometry, material);
        this.castGeometry.castShadow = true;
        this.castGeometry.receiveShadow = true;
        this.scene.add(this.castGeometry);
    }
    
    visualizeHotspots(hotspots) {
        // Clear previous hotspots
        this.scene.children
            .filter(c => c.userData.isHotspot)
            .forEach(c => this.scene.remove(c));
        
        hotspots.forEach((hs, i) => {
            const geometry = new THREE.SphereGeometry(8, 16, 16);
            const material = new THREE.MeshPhongMaterial({
                color: hs.severity === 'high' ? 0xff4444 : 0xff8844,
                transparent: true,
                opacity: 0.6
            });
            
            const sphere = new THREE.Mesh(geometry, material);
            sphere.position.set(
                hs.position[0] - 50,
                hs.position[1] - 30,
                hs.position[2] - 40
            );
            sphere.userData.isHotspot = true;
            
            this.scene.add(sphere);
        });
    }
    
    visualizeRisers(risers) {
        // Clear previous risers
        this.scene.children
            .filter(c => c.userData.isRiser)
            .forEach(c => this.scene.remove(c));
        
        risers.forEach((riser, i) => {
            const geometry = new THREE.CylinderGeometry(
                riser.radius, riser.radius, riser.height, 32
            );
            const material = new THREE.MeshPhongMaterial({
                color: 0x00d4ff,
                transparent: true,
                opacity: 0.7
            });
            
            const cylinder = new THREE.Mesh(geometry, material);
            cylinder.position.set(
                riser.position[0] - 50,
                riser.position[1] - 30 + riser.height / 2,
                riser.position[2] - 40
            );
            cylinder.userData.isRiser = true;
            
            this.scene.add(cylinder);
        });
    }
    
    visualizeDefects(defects) {
        // Clear previous defects
        this.scene.children
            .filter(c => c.userData.isDefect)
            .forEach(c => this.scene.remove(c));
        
        defects.forEach((defect, i) => {
            const geometry = new THREE.SphereGeometry(5, 16, 16);
            const material = new THREE.MeshPhongMaterial({
                color: 0xff0000,
                transparent: true,
                opacity: 0.8
            });
            
            const sphere = new THREE.Mesh(geometry, material);
            sphere.position.set(
                defect.position[0] - 50,
                defect.position[1] - 30,
                defect.position[2] - 40
            );
            sphere.userData.isDefect = true;
            
            this.scene.add(sphere);
        });
    }
    
    updateVisualization(data) {
        if (data.hotspots) {
            this.visualizeHotspots(data.hotspots);
        }
        if (data.risers) {
            this.visualizeRisers(data.risers);
        }
    }
    
    // ==================== UI HELPERS ====================
    
    hideDropZone() {
        document.getElementById('dropZone').classList.add('hidden');
    }
    
    showStatsOverlay() {
        document.getElementById('statsOverlay').style.display = 'block';
    }
    
    updateStats(geometry) {
        if (geometry.volume) {
            document.getElementById('statVolume').textContent = 
                (geometry.volume / 1000).toFixed(1) + ' cm³';
        }
        if (geometry.hotspots) {
            document.getElementById('statHotspots').textContent = 
                geometry.hotspots.length;
        }
        if (geometry.risers !== undefined) {
            document.getElementById('statRisers').textContent = geometry.risers;
        }
        if (geometry.yield !== undefined) {
            document.getElementById('statYield').textContent = 
                geometry.yield.toFixed(1) + '%';
        }
    }
    
    showProgress(title, percent) {
        document.getElementById('progressTitle').textContent = title;
        document.getElementById('progressFill').style.width = percent + '%';
        document.getElementById('progressText').textContent = percent + '%';
        document.getElementById('progressOverlay').classList.add('active');
    }
    
    updateProgress(data) {
        if (data.percent !== undefined) {
            document.getElementById('progressFill').style.width = data.percent + '%';
            document.getElementById('progressText').textContent = 
                Math.round(data.percent) + '%';
        }
        if (data.message) {
            document.getElementById('progressTitle').textContent = data.message;
        }
    }
    
    hideProgress() {
        document.getElementById('progressOverlay').classList.remove('active');
    }
    
    showSimulationResults() {
        if (!this.simulationResults) return;
        
        // Could open a modal or expand the view
        console.log('Simulation results:', this.simulationResults);
    }
}

// Initialize app
const app = new MetalGPTApp();
