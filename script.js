const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector(".nav-links");
const revealItems = document.querySelectorAll(".reveal");
const productTitle = document.querySelector(".product-copy h2");
const productText = document.querySelector(".product-copy p:not(.eyebrow)");
const productTags = document.querySelector(".product-tags");
const productBadges = document.querySelector(".product-badges");
const productSeal = document.querySelector(".floating-seal");
const productBuyButton = document.querySelector(".product-buy-button");
const productDisplay = document.querySelector(".product-display");
const productPrev = document.querySelector(".product-arrow-prev");
const productNext = document.querySelector(".product-arrow-next");
const siteHeader = document.querySelector(".site-header");
const heroVisual = document.querySelector(".hero-visual");
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const isMobileViewport = window.matchMedia("(max-width: 760px)");
const WHATSAPP_PHONE = "5524999380461";

const productSlides = [
  {
    title: "Rações",
    text: "A ração de todo mês, aquela fórmula que o veterinário indicou e opções para pets mais exigentes. A gente ajuda a comparar sem transformar escolha simples em dor de cabeça.",
    tags: ["Cães adultos", "Gatos", "Filhotes", "Super premium"],
    badges: ["favorito dos tutores", "chegou de novo"],
    seal: "mais vendido",
    visual: "racoes",
  },
  {
    title: "Petiscos",
    text: "Petiscos para treino, recompensa ou só pra ver aquele rabinho balançando. Tem opção para agradar sem exagero e para variar o mimo da semana.",
    tags: ["Bifinhos", "Sachês", "Recompensa", "Mimos rápidos"],
    badges: ["leve 18 pague 15", "promo da semana"],
    seal: "queridinho dos pets",
    visual: "petiscos",
  },
  {
    title: "Cuidados",
    text: "Guias, comedouros, brinquedos e itens de rotina para deixar o dia a dia mais prático. Coisas simples, mas que fazem diferença em casa.",
    tags: ["Higiene", "Brinquedos", "Passeio", "Acessórios"],
    badges: ["favorito dos tutores", "chegou de novo"],
    seal: "para levar hoje",
    visual: "cuidados",
  },
  {
    title: "Banho e Tosa",
    text: "Banho gostoso, tosa caprichada e aquele cuidado para o pet voltar cheiroso, leve e pronto para ganhar carinho em casa.",
    tags: ["Banho", "Tosa", "Higiene", "Agendamento"],
    badges: ["agenda aberta", "cuidado no detalhe"],
    seal: "saindo cheiroso",
    visual: "banho",
  },
];

let activeProductSlide = 0;
let scrollTicking = false;

document.body.classList.add("page-ready");

function updateScrollEffects() {
  siteHeader.classList.toggle("scrolled", window.scrollY > 24);
  if (!isMobileViewport.matches && !prefersReducedMotion.matches) {
    document.documentElement.style.setProperty("--scroll-shift", `${Math.min(window.scrollY * 0.04, 18)}px`);
  }
  scrollTicking = false;
}

window.addEventListener(
  "scroll",
  () => {
    if (scrollTicking) {
      return;
    }

    scrollTicking = true;
    window.requestAnimationFrame(updateScrollEffects);
  },
  { passive: true }
);

updateScrollEffects();

if (heroVisual && !isMobileViewport.matches && !prefersReducedMotion.matches) {
  heroVisual.addEventListener("pointermove", (event) => {
    const rect = heroVisual.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width - 0.5) * 14;
    const y = ((event.clientY - rect.top) / rect.height - 0.5) * 14;
    heroVisual.style.setProperty("--mx", `${x}px`);
    heroVisual.style.setProperty("--my", `${y}px`);
  });

  heroVisual.addEventListener("pointerleave", () => {
    heroVisual.style.setProperty("--mx", "0px");
    heroVisual.style.setProperty("--my", "0px");
  });
}

menuButton.addEventListener("click", () => {
  const isOpen = navigation.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});

navigation.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    navigation.classList.remove("open");
    menuButton.setAttribute("aria-expanded", "false");
  });
});

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.16 }
);

revealItems.forEach((item) => observer.observe(item));

function getWhatsappProductLink(serviceName) {
  const message = `Olá, gostaria de mais informações sobre ${serviceName}`;
  return `https://api.whatsapp.com/send/?phone=${WHATSAPP_PHONE}&text=${encodeURIComponent(message)}&type=phone_number&app_absent=0`;
}

function renderProductSlide(index) {
  const slide = productSlides[index];

  productTitle.textContent = slide.title;
  productText.textContent = slide.text;
  productTags.innerHTML = slide.tags.map((tag) => `<span>${tag}</span>`).join("");
  productBadges.innerHTML = slide.badges.map((badge) => `<span>${badge}</span>`).join("");
  productSeal.textContent = slide.seal;
  productBuyButton.href = getWhatsappProductLink(slide.title);
  productDisplay.dataset.visual = slide.visual;
  productDisplay.classList.remove("switching");
  window.requestAnimationFrame(() => productDisplay.classList.add("switching"));
}

function moveProductSlide(direction) {
  activeProductSlide =
    (activeProductSlide + direction + productSlides.length) % productSlides.length;
  renderProductSlide(activeProductSlide);
}

if (productPrev && productNext) {
  renderProductSlide(activeProductSlide);
  productPrev.addEventListener("click", () => moveProductSlide(-1));
  productNext.addEventListener("click", () => moveProductSlide(1));
}

function getWhatsappBuyLink(product) {
  const message = `Olá, gostaria de comprar o produto ${product.nome} no valor de ${product.preco_formatado}`;
  return `https://api.whatsapp.com/send/?phone=${WHATSAPP_PHONE}&text=${encodeURIComponent(message)}&type=phone_number&app_absent=0`;
}

function createProductCard(product) {
  const article = document.createElement("article");
  article.className = "store-product-card";

  const photoWrap = document.createElement("div");
  photoWrap.className = "store-product-photo";

  const photo = document.createElement("img");
  photo.src = product.foto_url;
  photo.alt = product.nome;
  photo.loading = "lazy";
  photoWrap.append(photo);

  const info = document.createElement("div");
  info.className = "store-product-info";

  const title = document.createElement("h3");
  title.textContent = product.nome;

  const price = document.createElement("p");
  price.textContent = product.preco_formatado;

  const buyButton = document.createElement("a");
  buyButton.className = "product-buy-button";
  buyButton.href = getWhatsappBuyLink(product);
  buyButton.target = "_blank";
  buyButton.rel = "noreferrer";
  buyButton.innerHTML = '<img src="assets/whatsapp-icon.webp" alt="" width="25" height="25" decoding="async" />Comprar';

  info.append(title, price, buyButton);
  article.append(photoWrap, info);

  return article;
}

function renderDynamicProducts(products) {
  const productsGrid = document.querySelector("[data-products-grid]");
  const productsEmpty = document.querySelector("[data-products-empty]");
  if (!productsGrid || !productsEmpty) {
    return;
  }

  if (products.length) {
    productsGrid.replaceChildren(...products.map(createProductCard));
    productsGrid.hidden = false;
    productsEmpty.hidden = true;
  } else {
    productsGrid.replaceChildren();
    productsGrid.hidden = true;
    productsEmpty.hidden = false;
  }
}
function fetchProducts() {
  return fetch("/api/produtos").then((response) =>
    response.ok ? response.json() : Promise.reject(response)
  );
}

if (!document.querySelector("[data-products-grid] .store-product-card")) {
  fetchProducts()
    .then(renderDynamicProducts)
    .catch(() => {});
}
