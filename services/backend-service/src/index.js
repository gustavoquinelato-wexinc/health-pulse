import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const port = process.env.PORT || 3001;

app.use(cors());
app.get('/', (req, res) => {
  res.send('Backend Service is running');
});

app.listen(port, () => {
  console.log(`Backend service listening at http://localhost:${port}`);
});
