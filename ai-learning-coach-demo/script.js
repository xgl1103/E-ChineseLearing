const views = document.querySelectorAll(".view");
const navItems = document.querySelectorAll(".nav-item");

function setActiveView(viewId) {
  views.forEach((view) => view.classList.toggle("active", view.id === viewId));
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.view === viewId));
}

navItems.forEach((item) => {
  item.addEventListener("click", () => setActiveView(item.dataset.view));
});

function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

window.addEventListener("load", refreshIcons);

const learningPath = document.querySelector("#learningPath");
const pathVariants = [
  [
    ["复习家庭成员表达", "已完成 · 正确率 92%", "done"],
    ["餐厅点餐与数量表达", "进行中 · 建议 15 分钟/天", "active"],
    ["录音纠音: 三声变调", "待开始 · AI 语音反馈", ""],
  ],
  [
    ["听力复现: 服务员提问", "已完成 · 正确率 88%", "done"],
    ["价格问答: 多少钱", "进行中 · 建议 12 分钟/天", "active"],
    ["小作文: 我喜欢的餐厅", "待开始 · 老师下节课点评", ""],
  ],
];
let pathIndex = 0;

document.querySelector("#rebalancePath").addEventListener("click", () => {
  pathIndex = (pathIndex + 1) % pathVariants.length;
  learningPath.innerHTML = pathVariants[pathIndex]
    .map(
      ([title, detail, state]) => `
        <div class="timeline-item ${state}">
          <span></span>
          <div>
            <strong>${title}</strong>
            <p>${detail}</p>
          </div>
        </div>
      `
    )
    .join("");
});

const generatedPlans = [
  "本周计划已生成: 3 次餐厅场景 AI 陪练、1 次录音纠音、1 份给老师的课堂复盘。",
  "本周计划已生成: 重点复习量词，周三推送家长报告，周五同步下节课备课建议。",
];
let planIndex = 0;

document.querySelector("#generatePlan").addEventListener("click", (event) => {
  const button = event.currentTarget;
  button.innerHTML = `<i data-lucide="check"></i>${generatedPlans[planIndex]}`;
  planIndex = (planIndex + 1) % generatedPlans.length;
  refreshIcons();
  window.setTimeout(() => {
    button.innerHTML = `<i data-lucide="sparkles"></i>生成本周计划`;
    refreshIcons();
  }, 2600);
});

document.querySelector("#refreshData").addEventListener("click", () => {
  const score = document.querySelector(".radial-score");
  const nextScore = score.style.getPropertyValue("--score").trim() === "76" ? "82" : "76";
  score.style.setProperty("--score", nextScore);
  score.querySelector("span").textContent = nextScore;
});

const chatWindow = document.querySelector("#chatWindow");
const practiceInput = document.querySelector("#practiceInput");

function appendMessage(role, speaker, content, extraClass = "") {
  const message = document.createElement("div");
  message.className = `message ${role} ${extraClass}`.trim();
  message.innerHTML = `<span>${speaker}</span><p>${content}</p>`;
  chatWindow.appendChild(message);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

document.querySelector("#sendPractice").addEventListener("click", () => {
  const value = practiceInput.value.trim();
  if (!value) return;
  appendMessage("user", "Alex", value);
  window.setTimeout(() => {
    appendMessage(
      "ai",
      "AI",
      "表达很完整。下一步请加一句：“一共多少钱？”这样就能完成真实点餐对话。",
      "feedback"
    );
  }, 420);
});

const prompts = [
  "请用中文问服务员：“这份饺子多少钱？”",
  "请说出你不想要辣的食物。",
  "请用“一杯”和“一碗”各造一个句子。",
];
let promptIndex = 0;

document.querySelector("#nextPrompt").addEventListener("click", () => {
  appendMessage("ai", "AI", prompts[promptIndex]);
  promptIndex = (promptIndex + 1) % prompts.length;
});

document.querySelector("#copyBrief").addEventListener("click", async (event) => {
  const brief = document.querySelector("#teacherBrief").innerText;
  await navigator.clipboard?.writeText(brief);
  event.currentTarget.innerHTML = `<i data-lucide="check"></i>已复制`;
  refreshIcons();
  window.setTimeout(() => {
    event.currentTarget.innerHTML = `<i data-lucide="copy"></i>复制`;
    refreshIcons();
  }, 1600);
});

document.querySelector("#generatorForm").addEventListener("submit", (event) => {
  event.preventDefault();
  document.querySelector("#teacherBrief").innerHTML = `
    <h3>AI 生成活动: 餐厅角色扮演</h3>
    <ul>
      <li>老师展示 6 张食物图片，学生用“一杯/一份/一碗”描述。</li>
      <li>AI 随机给出价格，学生完成“多少钱”和“我要……”句型。</li>
      <li>结束后生成 3 句家庭练习，自动同步到家长报告。</li>
    </ul>
  `;
});

const reportCopy = document.querySelector("#reportCopy");
let warmTone = true;

document.querySelector("#toneToggle").addEventListener("click", () => {
  warmTone = !warmTone;
  reportCopy.innerHTML = warmTone
    ? `
      <p>Alex 今天能够用中文完成基础点餐对话，尤其在“我想要……”句型上进步明显。</p>
      <p>需要继续练习的是量词，比如“一杯果汁”“一份面条”。本周建议每天完成 10 分钟 AI 陪练，重点做餐厅场景问答。</p>
      <p>下节课老师会继续用角色扮演帮助 Alex 把句型说得更自然。</p>
    `
    : `
      <p>本节课目标为餐厅点餐表达。Alex 已掌握“我想要……”基础句型，能完成 3 轮以上问答。</p>
      <p>当前薄弱点为量词匹配和三声变调。系统已生成 5 个课后练习任务，并会将完成情况同步给任课老师。</p>
      <p>建议家长本周提醒 Alex 完成每日 10 分钟练习，以提升课堂内容复现率。</p>
    `;
});

document.querySelector("#sendReport").addEventListener("click", () => {
  const note = document.querySelector("#sendNote");
  note.textContent = "报告已发送。家长打开后会记录阅读状态。";
});
