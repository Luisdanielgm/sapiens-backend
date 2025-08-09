"""
Ejemplos de plantillas HTML para el sistema de plantillas de SapiensIA.
Estos ejemplos demuestran el uso de marcadores de personalización.
"""

MINDMAP_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-sapiens-param="title">Mapa Mental Interactivo</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: data-sapiens-param="background_color";
        }
        .mindmap-container {
            width: 100%;
            height: 600px;
            position: relative;
            border: 2px solid data-sapiens-param="border_color";
            border-radius: 10px;
            overflow: hidden;
        }
        .central-node {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: data-sapiens-param="central_node_size";
            height: data-sapiens-param="central_node_size";
            background: data-sapiens-param="central_node_color";
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: data-sapiens-param="central_font_size";
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .branch-node {
            position: absolute;
            background: data-sapiens-param="branch_color";
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: data-sapiens-param="branch_font_size";
        }
        .branch-node:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 12px rgba(0,0,0,0.3);
        }
        .connection-line {
            position: absolute;
            height: 2px;
            background: data-sapiens-param="line_color";
            transform-origin: left center;
        }
        
        .instructions {
            margin-bottom: 20px;
            padding: 15px;
            background: #f0f8ff;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        
        .controls {
            margin-top: 20px;
            text-align: center;
        }
        
        .btn {
            background: data-sapiens-param="button_color";
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 0 5px;
            font-size: 14px;
        }
        
        .btn:hover {
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="instructions">
        <h3>Instrucciones</h3>
        <p data-sapiens-slot="instructions">Haz clic en el nodo central para explorar los conceptos relacionados. Cada rama representa un tema importante que debes estudiar.</p>
    </div>
    
    <div class="mindmap-container" id="mindmapContainer">
        <div class="central-node" id="centralNode">
            <span data-sapiens-param="central_concept">Concepto Principal</span>
        </div>
    </div>
    
    <div class="controls">
        <button class="btn" onclick="resetMindmap()" data-sapiens-if="show_reset">Reiniciar</button>
        <button class="btn" onclick="expandAll()" data-sapiens-if="show_expand">Expandir Todo</button>
        <button class="btn" onclick="showSummary()" data-sapiens-if="show_summary">Resumen</button>
    </div>
    
    <script id="sapiens-defaults" type="application/json">
    {
        "title": "Mapa Mental Interactivo",
        "background_color": "#f5f5f5",
        "border_color": "#2196F3",
        "central_node_size": "120px",
        "central_node_color": "#2196F3",
        "central_font_size": "16px",
        "branch_color": "#4CAF50",
        "branch_font_size": "14px",
        "line_color": "#666",
        "button_color": "#FF9800",
        "central_concept": "Tema Principal",
        "instructions": "Explora el mapa mental haciendo clic en los nodos para descubrir conceptos relacionados.",
        "show_reset": true,
        "show_expand": true,
        "show_summary": true
    }
    </script>
    
    <script>
        // Datos de los nodos (estos vendrían de los props de la instancia)
        const branches = [
            { text: data-sapiens-param="branch_1", angle: 0, distance: 180 },
            { text: data-sapiens-param="branch_2", angle: 72, distance: 180 },
            { text: data-sapiens-param="branch_3", angle: 144, distance: 180 },
            { text: data-sapiens-param="branch_4", angle: 216, distance: 180 },
            { text: data-sapiens-param="branch_5", angle: 288, distance: 180 }
        ];
        
        let isExpanded = false;
        
        function initializeMindmap() {
            const container = document.getElementById('mindmapContainer');
            const centralNode = document.getElementById('centralNode');
            
            // Crear nodos de rama
            branches.forEach((branch, index) => {
                if (branch.text && branch.text.trim()) {
                    createBranchNode(branch, index, container);
                    createConnectionLine(branch, container);
                }
            });
            
            // Evento click en nodo central
            centralNode.addEventListener('click', toggleExpansion);
        }
        
        function createBranchNode(branch, index, container) {
            const node = document.createElement('div');
            node.className = 'branch-node';
            node.textContent = branch.text;
            node.id = `branch-${index}`;
            node.style.opacity = '0';
            node.style.transform = 'scale(0)';
            
            // Calcular posición
            const centerX = container.offsetWidth / 2;
            const centerY = container.offsetHeight / 2;
            const radian = (branch.angle * Math.PI) / 180;
            const x = centerX + Math.cos(radian) * branch.distance - 50;
            const y = centerY + Math.sin(radian) * branch.distance - 20;
            
            node.style.left = x + 'px';
            node.style.top = y + 'px';
            
            node.addEventListener('click', () => showBranchDetails(branch.text));
            
            container.appendChild(node);
        }
        
        function createConnectionLine(branch, container) {
            const line = document.createElement('div');
            line.className = 'connection-line';
            line.style.opacity = '0';
            
            // Calcular posición y rotación de la línea
            const centerX = container.offsetWidth / 2;
            const centerY = container.offsetHeight / 2;
            const radian = (branch.angle * Math.PI) / 180;
            const length = branch.distance - 60;
            
            line.style.left = centerX + 'px';
            line.style.top = centerY + 'px';
            line.style.width = length + 'px';
            line.style.transform = `rotate(${branch.angle}deg)`;
            
            container.appendChild(line);
        }
        
        function toggleExpansion() {
            const branches = document.querySelectorAll('.branch-node');
            const lines = document.querySelectorAll('.connection-line');
            
            if (!isExpanded) {
                // Mostrar ramas
                branches.forEach((node, index) => {
                    setTimeout(() => {
                        node.style.opacity = '1';
                        node.style.transform = 'scale(1)';
                    }, index * 100);
                });
                
                lines.forEach((line, index) => {
                    setTimeout(() => {
                        line.style.opacity = '1';
                    }, index * 100);
                });
                
                isExpanded = true;
            } else {
                // Ocultar ramas
                branches.forEach(node => {
                    node.style.opacity = '0';
                    node.style.transform = 'scale(0)';
                });
                
                lines.forEach(line => {
                    line.style.opacity = '0';
                });
                
                isExpanded = false;
            }
        }
        
        function expandAll() {
            if (!isExpanded) {
                toggleExpansion();
            }
        }
        
        function resetMindmap() {
            const branches = document.querySelectorAll('.branch-node');
            const lines = document.querySelectorAll('.connection-line');
            
            branches.forEach(node => {
                node.style.opacity = '0';
                node.style.transform = 'scale(0)';
            });
            
            lines.forEach(line => {
                line.style.opacity = '0';
            });
            
            isExpanded = false;
        }
        
        function showBranchDetails(branchText) {
            alert(`Explorando: ${branchText}\\n\\nEste es el lugar donde se mostraría información detallada sobre este concepto.`);
        }
        
        function showSummary() {
            const centralConcept = document.querySelector('[data-sapiens-param="central_concept"]').textContent;
            const activeBranches = branches.filter(b => b.text && b.text.trim()).map(b => b.text);
            
            const summary = `Resumen del Mapa Mental\\n\\nConcepto Central: ${centralConcept}\\n\\nTemas relacionados:\\n${activeBranches.map(b => `• ${b}`).join('\\n')}`;
            alert(summary);
        }
        
        // Inicializar cuando la página carga
        document.addEventListener('DOMContentLoaded', initializeMindmap);
    </script>
</body>
</html>
"""

INTERACTIVE_QUIZ_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-sapiens-param="quiz_title">Quiz Interactivo</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, data-sapiens-param="bg_gradient_start", data-sapiens-param="bg_gradient_end");
            min-height: 100vh;
        }
        
        .quiz-container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .quiz-header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid data-sapiens-param="accent_color";
        }
        
        .quiz-title {
            color: data-sapiens-param="title_color";
            font-size: data-sapiens-param="title_size";
            margin-bottom: 10px;
        }
        
        .quiz-description {
            color: #666;
            font-size: 16px;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            margin: 20px 0;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: data-sapiens-param="progress_color";
            width: 0%;
            transition: width 0.3s ease;
        }
        
        .question-card {
            display: none;
            animation: slideIn 0.5s ease;
        }
        
        .question-card.active {
            display: block;
        }
        
        .question-text {
            font-size: data-sapiens-param="question_size";
            color: data-sapiens-param="question_color";
            margin-bottom: 20px;
            line-height: 1.6;
        }
        
        .question-image {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin: 15px 0;
            display: none;
        }
        
        .options-container {
            display: grid;
            gap: 15px;
        }
        
        .option {
            padding: 15px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            background: white;
            font-size: 16px;
        }
        
        .option:hover {
            border-color: data-sapiens-param="accent_color";
            background: #f8f9fa;
        }
        
        .option.selected {
            border-color: data-sapiens-param="accent_color";
            background: data-sapiens-param="accent_color";
            color: white;
        }
        
        .option.correct {
            border-color: #4CAF50;
            background: #4CAF50;
            color: white;
        }
        
        .option.incorrect {
            border-color: #f44336;
            background: #f44336;
            color: white;
        }
        
        .feedback {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            display: none;
        }
        
        .feedback.correct {
            background: #e8f5e8;
            border-left: 4px solid #4CAF50;
            color: #2e7d32;
        }
        
        .feedback.incorrect {
            background: #ffeaea;
            border-left: 4px solid #f44336;
            color: #c62828;
        }
        
        .controls {
            margin-top: 30px;
            text-align: center;
        }
        
        .btn {
            background: data-sapiens-param="button_color";
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin: 0 10px;
            transition: all 0.3s ease;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .results {
            display: none;
            text-align: center;
            padding: 30px;
        }
        
        .score {
            font-size: 48px;
            font-weight: bold;
            color: data-sapiens-param="score_color";
            margin-bottom: 20px;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(20px); }
            to { opacity: 1; transform: translateX(0); }
        }
    </style>
</head>
<body>
    <div class="quiz-container">
        <div class="quiz-header">
            <h1 class="quiz-title" data-sapiens-param="quiz_title">Quiz Interactivo</h1>
            <p class="quiz-description" data-sapiens-slot="description">Pon a prueba tus conocimientos con este quiz interactivo.</p>
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        
        <div id="questionsContainer">
            <!-- Las preguntas se generarán dinámicamente -->
        </div>
        
        <div class="controls">
            <button class="btn" id="prevBtn" onclick="previousQuestion()" disabled>Anterior</button>
            <button class="btn" id="nextBtn" onclick="nextQuestion()" disabled>Siguiente</button>
            <button class="btn" id="submitBtn" onclick="submitQuiz()" style="display: none;">Finalizar Quiz</button>
        </div>
        
        <div class="results" id="results">
            <div class="score" id="finalScore">0%</div>
            <h3>¡Quiz Completado!</h3>
            <p id="scoreMessage">Mensaje de resultado</p>
            <button class="btn" onclick="restartQuiz()">Repetir Quiz</button>
        </div>
    </div>
    
    <script id="sapiens-defaults" type="application/json">
    {
        "quiz_title": "Quiz de Conocimientos",
        "bg_gradient_start": "#667eea",
        "bg_gradient_end": "#764ba2",
        "accent_color": "#667eea",
        "title_color": "#333",
        "title_size": "32px",
        "progress_color": "#667eea",
        "question_size": "20px",
        "question_color": "#333",
        "button_color": "#667eea",
        "score_color": "#667eea",
        "description": "Responde las siguientes preguntas para evaluar tu comprensión del tema."
    }
    </script>
    
    <script>
        // Datos del quiz (vendrían de los props de la instancia)
        const quizData = {
            questions: [
                {
                    text: data-sapiens-param="question_1_text",
                    options: [
                        data-sapiens-param="question_1_option_1",
                        data-sapiens-param="question_1_option_2", 
                        data-sapiens-param="question_1_option_3",
                        data-sapiens-param="question_1_option_4"
                    ],
                    correct: data-sapiens-param="question_1_correct",
                    feedback: data-sapiens-param="question_1_feedback"
                },
                {
                    text: data-sapiens-param="question_2_text",
                    options: [
                        data-sapiens-param="question_2_option_1",
                        data-sapiens-param="question_2_option_2",
                        data-sapiens-param="question_2_option_3", 
                        data-sapiens-param="question_2_option_4"
                    ],
                    correct: data-sapiens-param="question_2_correct",
                    feedback: data-sapiens-param="question_2_feedback"
                }
            ]
        };
        
        let currentQuestion = 0;
        let answers = [];
        let showingFeedback = false;
        
        function initializeQuiz() {
            renderQuestions();
            updateProgress();
            updateControls();
        }
        
        function renderQuestions() {
            const container = document.getElementById('questionsContainer');
            container.innerHTML = '';
            
            quizData.questions.forEach((question, index) => {
                if (question.text && question.text.trim()) {
                    const questionCard = createQuestionCard(question, index);
                    container.appendChild(questionCard);
                }
            });
            
            showQuestion(0);
        }
        
        function createQuestionCard(question, index) {
            const card = document.createElement('div');
            card.className = 'question-card';
            card.id = `question-${index}`;
            
            const validOptions = question.options.filter(opt => opt && opt.trim());
            
            card.innerHTML = `
                <div class="question-text">${question.text}</div>
                <div class="options-container">
                    ${validOptions.map((option, optIndex) => `
                        <div class="option" onclick="selectOption(${index}, ${optIndex})">
                            ${option}
                        </div>
                    `).join('')}
                </div>
                <div class="feedback" id="feedback-${index}">
                    <strong>Explicación:</strong> ${question.feedback || 'Respuesta registrada.'}
                </div>
            `;
            
            return card;
        }
        
        function showQuestion(index) {
            document.querySelectorAll('.question-card').forEach(card => {
                card.classList.remove('active');
            });
            
            const questionCard = document.getElementById(`question-${index}`);
            if (questionCard) {
                questionCard.classList.add('active');
            }
            
            currentQuestion = index;
            updateProgress();
            updateControls();
        }
        
        function selectOption(questionIndex, optionIndex) {
            if (showingFeedback) return;
            
            const questionCard = document.getElementById(`question-${questionIndex}`);
            const options = questionCard.querySelectorAll('.option');
            
            // Limpiar selecciones anteriores
            options.forEach(opt => opt.classList.remove('selected'));
            
            // Marcar opción seleccionada
            options[optionIndex].classList.add('selected');
            
            // Guardar respuesta
            answers[questionIndex] = optionIndex;
            
            // Mostrar feedback después de un breve delay
            setTimeout(() => {
                showFeedback(questionIndex, optionIndex);
            }, 500);
        }
        
        function showFeedback(questionIndex, selectedOption) {
            const question = quizData.questions[questionIndex];
            const questionCard = document.getElementById(`question-${questionIndex}`);
            const options = questionCard.querySelectorAll('.option');
            const feedback = document.getElementById(`feedback-${questionIndex}`);
            
            const isCorrect = selectedOption === question.correct;
            
            // Marcar opciones
            options.forEach((opt, index) => {
                if (index === question.correct) {
                    opt.classList.add('correct');
                } else if (index === selectedOption && !isCorrect) {
                    opt.classList.add('incorrect');
                }
            });
            
            // Mostrar feedback
            feedback.className = `feedback ${isCorrect ? 'correct' : 'incorrect'}`;
            feedback.style.display = 'block';
            
            showingFeedback = true;
            updateControls();
        }
        
        function nextQuestion() {
            if (currentQuestion < quizData.questions.length - 1) {
                showingFeedback = false;
                showQuestion(currentQuestion + 1);
            }
        }
        
        function previousQuestion() {
            if (currentQuestion > 0) {
                showingFeedback = false;
                showQuestion(currentQuestion - 1);
            }
        }
        
        function updateProgress() {
            const progress = ((currentQuestion + 1) / quizData.questions.length) * 100;
            document.getElementById('progressFill').style.width = progress + '%';
        }
        
        function updateControls() {
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            const submitBtn = document.getElementById('submitBtn');
            
            prevBtn.disabled = currentQuestion === 0;
            
            if (currentQuestion === quizData.questions.length - 1) {
                nextBtn.style.display = 'none';
                submitBtn.style.display = showingFeedback ? 'inline-block' : 'none';
            } else {
                nextBtn.style.display = 'inline-block';
                nextBtn.disabled = !showingFeedback;
                submitBtn.style.display = 'none';
            }
        }
        
        function submitQuiz() {
            const score = calculateScore();
            showResults(score);
        }
        
        function calculateScore() {
            let correct = 0;
            answers.forEach((answer, index) => {
                if (answer === quizData.questions[index].correct) {
                    correct++;
                }
            });
            return Math.round((correct / quizData.questions.length) * 100);
        }
        
        function showResults(score) {
            document.querySelector('.quiz-container > *:not(.results)').forEach(el => {
                el.style.display = 'none';
            });
            
            const results = document.getElementById('results');
            const scoreElement = document.getElementById('finalScore');
            const messageElement = document.getElementById('scoreMessage');
            
            scoreElement.textContent = score + '%';
            
            let message = '';
            if (score >= 90) {
                message = '¡Excelente! Dominas muy bien el tema.';
            } else if (score >= 70) {
                message = '¡Buen trabajo! Tienes un buen entendimiento del tema.';
            } else if (score >= 50) {
                message = 'Resultado aceptable. Te recomendamos repasar algunos conceptos.';
            } else {
                message = 'Te sugerimos estudiar más el tema antes de continuar.';
            }
            
            messageElement.textContent = message;
            results.style.display = 'block';
        }
        
        function restartQuiz() {
            currentQuestion = 0;
            answers = [];
            showingFeedback = false;
            
            document.getElementById('results').style.display = 'none';
            document.querySelector('.quiz-container > *:not(.results)').forEach(el => {
                el.style.display = '';
            });
            
            initializeQuiz();
        }
        
        // Inicializar cuando la página carga
        document.addEventListener('DOMContentLoaded', initializeQuiz);
    </script>
</body>
</html>
"""
